const sections=[
  ['dashboard','Dashboard'],['agents','Agents'],['skills','Skills'],['knowledge','Knowledge'],['ontology','Ontology'],
  ['memory','Memory'],['tools','Tools & MCP'],['cache','Cache'],['observability','Observability']
];
const state={section:'dashboard',agents:[],skills:[],bases:[],concepts:[],relationships:[],selected:null};
const nav=document.querySelector('#nav'),content=document.querySelector('#content'),title=document.querySelector('#page-title');
const keyInput=document.querySelector('#api-key');
keyInput.value=localStorage.getItem('agent-platform-api-key')||'';
keyInput.onchange=()=>localStorage.setItem('agent-platform-api-key',keyInput.value.trim());

for(const [key,label] of sections){
  const button=document.createElement('button');button.className='nav-item';button.innerHTML='<span class="nav-label">'+label+'</span>';
  button.onclick=()=>openSection(key);button.dataset.key=key;nav.appendChild(button);
}
document.querySelector('#refresh-btn').onclick=()=>openSection(state.section,true);

async function api(path,options={}){
  const apiKey=keyInput.value.trim();
  const headers={...(options.body instanceof FormData?{}:{'Content-Type':'application/json'}),...(apiKey?{'X-API-Key':apiKey}:{}),...(options.headers||{})};
  const response=await fetch(path,{...options,headers});
  if(!response.ok){let message=response.statusText;try{const body=await response.json();message=body.detail||body.error?.message||JSON.stringify(body)}catch{}throw new Error(message)}
  if(response.status===204)return null;
  return response.json();
}
function toast(message){const el=document.querySelector('#toast');el.textContent=message;el.classList.add('show');setTimeout(()=>el.classList.remove('show'),2200)}
function esc(value){return String(value??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[m]))}
function setActive(){document.querySelectorAll('.nav-item').forEach(x=>x.classList.toggle('active',x.dataset.key===state.section))}
async function checkHealth(){
  try{await api('/health/ready');document.querySelector('#health-dot').className='dot ok';document.querySelector('#health-label').textContent='Platform ready'}
  catch{document.querySelector('#health-dot').className='dot bad';document.querySelector('#health-label').textContent='Platform not ready'}
}
async function openSection(section){
  state.section=section;state.selected=null;setActive();title.textContent=sections.find(x=>x[0]===section)[1];content.innerHTML='<div class="empty">Loading…</div>';
  try{
    if(section==='dashboard')await dashboard();
    if(section==='agents')await definitions('agents');
    if(section==='skills')await definitions('skills');
    if(section==='knowledge')await knowledge();
    if(section==='ontology')await ontology();
    if(section==='memory')await memory();
    if(section==='tools')await tools();
    if(section==='cache')await cache();
    if(section==='observability')await observability();
  }catch(error){content.innerHTML='<div class="panel"><strong>Request failed</strong><div class="pre">'+esc(error.message)+'</div></div>'}
}
async function dashboard(){
  const [overview,config]=await Promise.all([api('/v1/admin/overview'),api('/v1/admin/config')]);const c=overview.counts;
  content.innerHTML='<div class="grid cards">'+[['Agents',c.agents],['Skills',c.skills],['Knowledge bases',c.knowledge_bases],['Ontology concepts',c.ontology_concepts],['Relationships',c.ontology_relationships],['MCP servers',c.mcp_servers]].map(x=>'<article class="card"><div class="label">'+x[0].toUpperCase()+'</div><div class="value">'+x[1]+'</div></article>').join('')+'</div><section class="panel"><div class="panel-head"><h2>Runtime configuration</h2></div><div class="status-line"><span class="status-chip"><b>Embedding</b> '+esc(config.embedding.provider)+' / '+esc(config.embedding.model)+'</span><span class="status-chip"><b>Cache</b> '+esc(config.cache.backend)+'</span><span class="status-chip"><b>Observability</b> '+(config.observability.enabled?'enabled':'disabled')+'</span><span class="status-chip"><b>API key</b> '+(config.hardening?.api_key_enabled?'enabled':'disabled')+'</span></div></section>';
}
async function definitions(kind){
  const items=await api('/v1/'+kind);state[kind]=items;content.innerHTML='<section class="panel"><div class="panel-head"><h2>'+kind+'</h2></div><div class="split"><div class="list" id="definition-list"></div><div><textarea id="definition-editor" class="editor"></textarea><div class="toolbar" style="margin-top:10px"><button class="primary" id="save-definition">Save changes</button></div></div></div></section>';
  const list=document.querySelector('#definition-list'),editor=document.querySelector('#definition-editor');
  items.forEach((item,index)=>{const b=document.createElement('button');b.innerHTML='<strong>'+esc(item.name)+'</strong><br><span class="muted mono">'+esc(item.key)+' · v'+item.version+'</span>';b.onclick=()=>{state.selected=item;editor.value=JSON.stringify(item,null,2);document.querySelectorAll('#definition-list button').forEach(x=>x.classList.remove('active'));b.classList.add('active')};list.appendChild(b);if(index===0)b.click()});
  document.querySelector('#save-definition').onclick=async()=>{if(!state.selected)return;const body=JSON.parse(editor.value);const saved=await api('/v1/'+kind+'/'+encodeURIComponent(state.selected.key),{method:'PUT',body:JSON.stringify(body)});editor.value=JSON.stringify(saved,null,2);toast('Saved')};
}
async function knowledge(){
  const bases=await api('/v1/knowledge-bases');content.innerHTML='<section class="panel"><div class="panel-head"><h2>Knowledge bases</h2></div><div class="split"><div class="list" id="base-list"></div><div id="documents"><div class="empty">Select a knowledge base.</div></div></div></section>';const list=document.querySelector('#base-list');
  bases.forEach(base=>{const b=document.createElement('button');b.innerHTML='<strong>'+esc(base.name)+'</strong><br><span class="mono muted">'+esc(base.key)+'</span>';b.onclick=()=>loadDocuments(base,b);list.appendChild(b)});
}
async function loadDocuments(base,button){
  document.querySelectorAll('#base-list button').forEach(x=>x.classList.remove('active'));button.classList.add('active');const docs=await api('/v1/knowledge-bases/'+encodeURIComponent(base.key)+'/documents');
  document.querySelector('#documents').innerHTML='<div class="panel-head"><h2>'+esc(base.name)+'</h2><label class="small-btn">Upload file<input id="file-upload" type="file" hidden></label></div><div class="table-wrap"><table><tbody>'+docs.map(d=>'<tr><td><strong>'+esc(d.title)+'</strong><br><span class="mono muted">'+esc(d.id)+'</span></td><td><span class="pill '+(d.status==='READY'?'on':'')+'">'+esc(d.status)+'</span></td><td>'+esc(d.media_type)+'</td></tr>').join('')+'</tbody></table></div>';
  document.querySelector('#file-upload').onchange=async e=>{const file=e.target.files[0];if(!file)return;const data=new FormData();data.append('file',file);await api('/v1/knowledge-bases/'+encodeURIComponent(base.key)+'/files',{method:'POST',body:data});toast('Uploaded and ingested');await loadDocuments(base,button)};
}
async function ontology(){
  const [concepts,relationships]=await Promise.all([api('/v1/ontology/concepts'),api('/v1/ontology/relationships')]);content.innerHTML='<section class="panel"><div class="panel-head"><h2>Ontology</h2></div><div class="pre">'+esc(JSON.stringify({concepts,relationships},null,2))+'</div></section>';
}
async function memory(){content.innerHTML='<section class="panel"><div class="panel-head"><h2>Memory recall</h2></div><div class="toolbar"><select id="memory-type"><option>correlation</option><option>agent</option><option>global</option><option>custom</option></select><input id="memory-key" placeholder="scope key"><button class="primary" id="recall-memory">Recall</button></div><div id="memory-results"></div></section>';document.querySelector('#recall-memory').onclick=async()=>{const items=await api('/v1/memory/recall',{method:'POST',body:JSON.stringify({scopes:[{type:val('memory-type'),key:val('memory-key')}],kinds:[],min_importance:0,limit:20})});document.querySelector('#memory-results').innerHTML='<div class="pre">'+esc(JSON.stringify(items,null,2))+'</div>'}}
async function tools(){const [servers,tools]=await Promise.all([api('/v1/mcp/servers'),api('/v1/tools?refresh=true').catch(e=>({error:e.message}))]);content.innerHTML='<section class="panel"><div class="panel-head"><h2>Tools & MCP</h2></div><div class="pre">'+esc(JSON.stringify({servers,tools},null,2))+'</div></section>'}
async function cache(){const stats=await api('/v1/cache/stats');content.innerHTML='<section class="panel"><div class="panel-head"><h2>Cache</h2></div><div class="pre">'+esc(JSON.stringify(stats,null,2))+'</div></section>'}
async function observability(){const config=await api('/v1/admin/config');content.innerHTML='<section class="panel"><div class="panel-head"><h2>Observability</h2></div><div class="status-line"><span class="status-chip"><b>OTel</b> '+(config.observability.enabled?'enabled':'disabled')+'</span></div><div class="toolbar" style="margin-top:14px"><a class="primary" href="/metrics" target="_blank">Metrics ↗</a><a class="secondary" href="'+esc(config.observability.jaeger_url)+'" target="_blank">Jaeger ↗</a></div></section>'}
function val(id){return document.querySelector('#'+id)?.value||''}
checkHealth();openSection('dashboard');
