import fs from "node:fs/promises";
import path from "node:path";
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { google, slides_v1 } from "googleapis";
import { z } from "zod";
import { getAuth } from "./google-auth.js";
import { REPO_ROOT } from "./paths.js";

const auth=await getAuth();
const drive=google.drive({version:"v3",auth});
const slides=google.slides({version:"v1",auth});
const docs=google.docs({version:"v1",auth});
const sheets=google.sheets({version:"v4",auth});
const server=new McpServer({name:"proposal-copilot-google-workspace",version:"0.2.0"});
function text(data:unknown){return {content:[{type:"text" as const,text:typeof data==="string"?data:JSON.stringify(data,null,2)}]};}
function escapeDrive(value:string){return value.replace(/\\/g,"\\\\").replace(/'/g,"\\'");}
function elementText(element:slides_v1.Schema$PageElement){const shape=element.shape?.text?.textElements?.map(x=>x.textRun?.content??"").join("").trim()??"";const table=element.table?.tableRows?.map(r=>r.tableCells?.map(c=>c.text?.textElements?.map(x=>x.textRun?.content??"").join("").trim()).join(" | ")).join("\n").trim()??"";return [shape,table].filter(Boolean).join("\n");}
function summarize(p:slides_v1.Schema$Presentation){return {presentationId:p.presentationId,title:p.title,pageSize:p.pageSize,slides:p.slides?.map((s,index)=>({index,objectId:s.objectId,slideProperties:s.slideProperties,pageElements:s.pageElements?.map(e=>({objectId:e.objectId,type:e.shape?"shape":e.image?"image":e.table?"table":e.line?"line":e.video?"video":e.wordArt?"wordArt":"other",text:elementText(e),size:e.size,transform:e.transform,shapeType:e.shape?.shapeType}))??[]}))??[],layouts:p.layouts?.map(l=>({objectId:l.objectId,layoutProperties:l.layoutProperties}))??[],masters:p.masters?.map(m=>({objectId:m.objectId}))??[]};}
function rawShapeText(element:slides_v1.Schema$PageElement){return element.shape?.text?.textElements?.map(x=>x.textRun?.content??"").join("")??"";}
function findPageElement(p:slides_v1.Schema$Presentation,objectId:string){for(const slide of p.slides??[]){for(const element of slide.pageElements??[]){if(element.objectId===objectId)return element;}}return undefined;}
async function safeSlideRequests(presentationId:string,requests:slides_v1.Schema$Request[]){
  const deleteRequests=requests.filter(r=>r.deleteText);
  if(deleteRequests.length===0)return requests;
  const presentation=(await slides.presentations.get({presentationId})).data;
  return requests.filter(request=>{
    const deletion=request.deleteText;
    if(!deletion)return true;
    const range=deletion.textRange;
    if(range?.type==="FIXED_RANGE"&&typeof range.startIndex==="number"&&typeof range.endIndex==="number"&&range.startIndex>=range.endIndex)return false;
    if(range?.type!=="ALL"||deletion.cellLocation)return true;
    const objectId=deletion.objectId;
    if(!objectId)return true;
    const element=findPageElement(presentation,objectId);
    if(!element||!element.shape)return true;
    return rawShapeText(element).length>0;
  });
}

const workspaceRoot=path.resolve(REPO_ROOT,"workspace");
async function resolveWorkspaceOutput(relativePath:string,overwrite:boolean){
  const normalized=relativePath.replace(/^\/+/,"");
  const output=path.resolve(REPO_ROOT,normalized);
  if(output!==workspaceRoot&&!output.startsWith(workspaceRoot+path.sep)){
    throw new Error("Drive downloads/exports may only be written under the repository workspace/ directory");
  }
  if(!overwrite){
    try{await fs.access(output);throw new Error(`Destination already exists: ${relativePath}. Set overwrite=true to replace it.`);}catch(error){if(error instanceof Error&&error.message.startsWith("Destination already exists:"))throw error;}
  }
  await fs.mkdir(path.dirname(output),{recursive:true});
  return output;
}

const driveFields="id,name,mimeType,parents,webViewLink,modifiedTime,createdTime,owners(displayName,emailAddress),size,md5Checksum,version";

server.tool("drive_search_files","Search accessible Google Drive files and folders. Read-only.",{name:z.string().optional(),mimeType:z.string().optional(),folderId:z.string().optional(),fullText:z.string().optional(),pageSize:z.number().int().min(1).max(100).default(20)},async({name,mimeType,folderId,fullText,pageSize})=>{const q=["trashed = false"];if(name)q.push(`name = '${escapeDrive(name)}'`);if(mimeType)q.push(`mimeType = '${escapeDrive(mimeType)}'`);if(folderId)q.push(`'${escapeDrive(folderId)}' in parents`);if(fullText)q.push(`fullText contains '${escapeDrive(fullText)}'`);const r=await drive.files.list({q:q.join(" and "),pageSize,spaces:"drive",orderBy:"modifiedTime desc",fields:`files(${driveFields})`});return text(r.data.files??[]);});
server.tool("drive_list_folder","List the direct children of one Google Drive folder for proposal source discovery. Read-only.",{folderId:z.string(),pageSize:z.number().int().min(1).max(1000).default(200)},async({folderId,pageSize})=>{const files=[];let pageToken:string|undefined;do{const r=await drive.files.list({q:`trashed = false and '${escapeDrive(folderId)}' in parents`,pageSize:Math.min(pageSize,1000),pageToken,spaces:"drive",orderBy:"name",fields:`nextPageToken,files(${driveFields})`,supportsAllDrives:true,includeItemsFromAllDrives:true});files.push(...(r.data.files??[]));pageToken=r.data.nextPageToken??undefined;}while(pageToken&&files.length<pageSize);return text(files.slice(0,pageSize));});
server.tool("drive_get_file","Get Drive file metadata. Read-only.",{fileId:z.string()},async({fileId})=>text((await drive.files.get({fileId,supportsAllDrives:true,fields:driveFields})).data));
server.tool("drive_download_file","Download a non-Google-native Drive file into workspace scratch storage.",{fileId:z.string(),outputPath:z.string(),overwrite:z.boolean().default(false)},async({fileId,outputPath,overwrite})=>{const meta=(await drive.files.get({fileId,supportsAllDrives:true,fields:"id,name,mimeType,size,md5Checksum,modifiedTime"})).data;if(meta.mimeType?.startsWith("application/vnd.google-apps."))throw new Error(`File ${meta.name??fileId} is Google-native (${meta.mimeType}); use a native API or drive_export_file instead.`);const output=await resolveWorkspaceOutput(outputPath,overwrite);const r=await drive.files.get({fileId,alt:"media",supportsAllDrives:true},{responseType:"arraybuffer"});const buffer=Buffer.from(r.data as ArrayBuffer);await fs.writeFile(output,buffer);return text({fileId,name:meta.name,mimeType:meta.mimeType,size:buffer.length,md5Checksum:meta.md5Checksum,modifiedTime:meta.modifiedTime,outputPath:path.relative(REPO_ROOT,output)});});
server.tool("drive_export_file","Export a Google-native Drive file into workspace scratch storage.",{fileId:z.string(),mimeType:z.string(),outputPath:z.string(),overwrite:z.boolean().default(false)},async({fileId,mimeType,outputPath,overwrite})=>{const meta=(await drive.files.get({fileId,supportsAllDrives:true,fields:"id,name,mimeType,modifiedTime"})).data;if(!meta.mimeType?.startsWith("application/vnd.google-apps."))throw new Error(`File ${meta.name??fileId} is not Google-native; use drive_download_file instead.`);const output=await resolveWorkspaceOutput(outputPath,overwrite);const r=await drive.files.export({fileId,mimeType},{responseType:"arraybuffer"});const buffer=Buffer.from(r.data as ArrayBuffer);await fs.writeFile(output,buffer);return text({fileId,name:meta.name,sourceMimeType:meta.mimeType,exportMimeType:mimeType,size:buffer.length,modifiedTime:meta.modifiedTime,outputPath:path.relative(REPO_ROOT,output)});});
server.tool("drive_copy_file","Copy a Drive file, optionally into a destination folder.",{fileId:z.string(),newName:z.string(),destinationFolderId:z.string().optional()},async({fileId,newName,destinationFolderId})=>text((await drive.files.copy({fileId,supportsAllDrives:true,requestBody:{name:newName,...(destinationFolderId?{parents:[destinationFolderId]}:{})},fields:"id,name,mimeType,parents,webViewLink,createdTime,modifiedTime"})).data));
server.tool("drive_create_folder","Create a Drive folder.",{name:z.string(),parentFolderId:z.string().optional()},async({name,parentFolderId})=>text((await drive.files.create({requestBody:{name,mimeType:"application/vnd.google-apps.folder",...(parentFolderId?{parents:[parentFolderId]}:{})},fields:"id,name,mimeType,parents,webViewLink"})).data));
server.tool("drive_move_file","Move a Drive file to another folder.",{fileId:z.string(),destinationFolderId:z.string()},async({fileId,destinationFolderId})=>{const c=await drive.files.get({fileId,fields:"parents",supportsAllDrives:true});const prev=c.data.parents?.join(",")??"";return text((await drive.files.update({fileId,addParents:destinationFolderId,removeParents:prev||undefined,supportsAllDrives:true,fields:"id,name,parents,webViewLink"})).data);});

server.tool("slides_create_presentation","Create a blank Google Slides presentation.",{title:z.string()},async({title})=>text((await slides.presentations.create({requestBody:{title}})).data));
server.tool("slides_get_presentation","Read Slides structure, IDs, text, transforms, layouts and masters. Read-only.",{presentationId:z.string()},async({presentationId})=>text(summarize((await slides.presentations.get({presentationId})).data)));
server.tool("slides_get_thumbnail","Fetch a PNG thumbnail of one slide for visual inspection. Read-only.",{presentationId:z.string(),slideObjectId:z.string(),size:z.enum(["SMALL","MEDIUM","LARGE"]).default("MEDIUM")},async({presentationId,slideObjectId,size})=>{const meta=await slides.presentations.pages.getThumbnail({presentationId,pageObjectId:slideObjectId,"thumbnailProperties.mimeType":"PNG","thumbnailProperties.thumbnailSize":size});if(!meta.data.contentUrl)throw new Error("Google Slides returned no thumbnail URL");const r=await fetch(meta.data.contentUrl);if(!r.ok)throw new Error(`Thumbnail download failed with HTTP ${r.status}`);const b=Buffer.from(await r.arrayBuffer());return {content:[{type:"image" as const,data:b.toString("base64"),mimeType:"image/png"},{type:"text" as const,text:JSON.stringify({presentationId,slideObjectId,width:meta.data.width,height:meta.data.height},null,2)}]};});
server.tool("slides_duplicate_slide","Duplicate a slide within a generated presentation.",{presentationId:z.string(),slideObjectId:z.string(),objectIds:z.record(z.string()).optional()},async({presentationId,slideObjectId,objectIds})=>{
  const response=await slides.presentations.batchUpdate({presentationId,requestBody:{requests:[{duplicateObject:{objectId:slideObjectId,...(objectIds?{objectIds}: {})}}]}});
  const duplicate=response.data.replies?.[0]?.duplicateObject;
  return text({objectId:duplicate?.objectId??objectIds?.[slideObjectId]??null,objectIds:objectIds??{}});
});
server.tool("slides_delete_slide","Delete a slide from a generated presentation.",{presentationId:z.string(),slideObjectId:z.string()},async({presentationId,slideObjectId})=>text((await slides.presentations.batchUpdate({presentationId,requestBody:{requests:[{deleteObject:{objectId:slideObjectId}}]}})).data));
server.tool("slides_move_slides","Move slides to a zero-based insertion index.",{presentationId:z.string(),slideObjectIds:z.array(z.string()).min(1),insertionIndex:z.number().int().min(0)},async({presentationId,slideObjectIds,insertionIndex})=>text((await slides.presentations.batchUpdate({presentationId,requestBody:{requests:[{updateSlidesPosition:{slideObjectIds,insertionIndex}}]}})).data));
server.tool("slides_replace_text","Replace exact text on selected slides.",{presentationId:z.string(),pageObjectIds:z.array(z.string()).min(1),replacements:z.array(z.object({from:z.string(),to:z.string(),matchCase:z.boolean().default(true)})).min(1)},async({presentationId,pageObjectIds,replacements})=>{const requests:slides_v1.Schema$Request[]=replacements.map(x=>({replaceAllText:{containsText:{text:x.from,matchCase:x.matchCase},replaceText:x.to,pageObjectIds}}));return text((await slides.presentations.batchUpdate({presentationId,requestBody:{requests}})).data);});
server.tool("slides_replace_element_text","Replace all text inside one specific text-bearing page element.",{presentationId:z.string(),elementObjectId:z.string(),text:z.string()},async({presentationId,elementObjectId,text:newText})=>{
  const presentation=(await slides.presentations.get({presentationId})).data;
  const element=findPageElement(presentation,elementObjectId);
  if(!element?.shape)throw new Error(`Element ${elementObjectId} is not a text-bearing shape in presentation ${presentationId}`);
  const currentText=rawShapeText(element);
  const requests:slides_v1.Schema$Request[]=[];
  if(currentText.length>0)requests.push({deleteText:{objectId:elementObjectId,textRange:{type:"ALL"}}});
  if(newText.length>0)requests.push({insertText:{objectId:elementObjectId,insertionIndex:0,text:newText}});
  if(requests.length===0)return text({presentationId,elementObjectId,updated:false,reason:"already-empty"});
  return text((await slides.presentations.batchUpdate({presentationId,requestBody:{requests}})).data);
});
server.tool("slides_batch_update","Advanced Slides API batchUpdate for generated presentations only.",{presentationId:z.string(),requests:z.array(z.record(z.any())).min(1)},async({presentationId,requests})=>{
  const normalized=await safeSlideRequests(presentationId,requests as slides_v1.Schema$Request[]);
  if(normalized.length===0)return text({presentationId,updated:false,reason:"all-requests-were-safe-noops"});
  return text((await slides.presentations.batchUpdate({presentationId,requestBody:{requests:normalized}})).data);
});

server.tool("docs_get_document","Read a Google Docs document. Read-only.",{documentId:z.string()},async({documentId})=>text((await docs.documents.get({documentId})).data));
server.tool("docs_create_document","Create a new Google Docs document.",{title:z.string()},async({title})=>text((await docs.documents.create({requestBody:{title}})).data));
server.tool("docs_batch_update","Apply Google Docs batchUpdate requests.",{documentId:z.string(),requests:z.array(z.record(z.any())).min(1)},async({documentId,requests})=>text((await docs.documents.batchUpdate({documentId,requestBody:{requests}})).data));

server.tool("sheets_get_spreadsheet","Read spreadsheet metadata and sheet structure.",{spreadsheetId:z.string()},async({spreadsheetId})=>text((await sheets.spreadsheets.get({spreadsheetId,includeGridData:false})).data));
server.tool("sheets_get_values","Read a range from Google Sheets.",{spreadsheetId:z.string(),range:z.string()},async({spreadsheetId,range})=>text((await sheets.spreadsheets.values.get({spreadsheetId,range})).data));
server.tool("sheets_update_values","Write values to a range in Google Sheets.",{spreadsheetId:z.string(),range:z.string(),values:z.array(z.array(z.any())),valueInputOption:z.enum(["RAW","USER_ENTERED"]).default("USER_ENTERED")},async({spreadsheetId,range,values,valueInputOption})=>text((await sheets.spreadsheets.values.update({spreadsheetId,range,valueInputOption,requestBody:{values}})).data));

await server.connect(new StdioServerTransport());
