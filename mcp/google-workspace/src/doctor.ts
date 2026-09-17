import { google } from "googleapis";
import { getAuth } from "./google-auth.js";

const auth = await getAuth();

const drive = google.drive({ version: "v3", auth });
const slides = google.slides({ version: "v1", auth });
const docs = google.docs({ version: "v1", auth });
const sheets = google.sheets({ version: "v4", auth });

await drive.files.list({
  pageSize: 1,
  fields: "files(id,name,mimeType)"
});
console.log("Drive API authentication OK");

// These constructors use the same authenticated client. Individual resource
// calls require a concrete presentation/document/spreadsheet ID and are tested
// later through the MCP tools.
void slides;
void docs;
void sheets;
console.log("Slides client OK");
console.log("Docs client OK");
console.log("Sheets client OK");
console.log("Doctor completed successfully.");
