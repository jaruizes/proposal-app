const sections=[
  ['dashboard','Dashboard'],['agents','Agents'],['skills','Skills'],['knowledge','Knowledge'],['ontology','Ontology'],
  ['memory','Memory'],['tools','Tools & MCP'],['cache','Cache'],['observability','Observability']
];
const state={section:'dashboard',agents:[],skills:[],bases:[],concepts:[],relationships:[],selected:null};
const nav=document.querySelector('#nav'),content=document.querySelector('#content'),title=document.querySelector('#page-title');

for(const [key,label] of sections){
  const button=document.createElement('button');button.className='nav-item';button.innerHTML='<span class="nav-label">'+label+'</span>';
  button.onclick=()=>openSection(key);button.dataset.key=key;nav.appendChild(button);
}
document.querySelector('#refresh-btn').onclick=()=>openSection(state.section,true);

async function api(path,options={}){
  const response=await fetch(path,{headers:{'Content-Type':'application/json',...(options.headers||{})},...options});
  if(!response.ok){let message=response.statusText;try{const body=await response.json();message=body.detail||JSON.stringify(body)}catch{}throw new Error(message)}
  if(response.status===204)return null;
  return response.json();
}
function toast(message){const el=document.querySelector('#toast');el.textContent=message;el.classList.add('show');setTimeout(()=>el.classList.remove('show'),2200)}
function esc(value){return String(value??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[m]))}
function setActive(){document.querySelectorAll('.nav-item').forEach(x=>x.classList.toggle('active',x.dataset.key===state.section))}
async function checkHealth(){
  try{await api('/health');document.querySelector('#health-dot').className='dot ok';document.querySelector('#health-label').textContent='Platform online'}
  catch{document.querySelector('#health-dot').className='dot bad';document.querySelector('#health-label').textContent='Platform unavailable'}
}

async function openSection(section,refresh=false){
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
  const [overview,config]=await Promise.all([api('/v1/admin/overview'),api('/v1/admin/config')]);
  const c=overview.counts;
  content.innerHTML=`
    <div class="grid cards">
      ${[['Agents',c.agents],['Skills',c.skills],['Knowledge bases',c.knowledge_bases],['Ontology concepts',c.ontology_concepts],['Relationships',c.ontology_relationships],['MCP servers',c.mcp_servers]].map(x=>`<article class="card"><div class="label">${x[0].toUpperCase()}</div><div class="value">${x[1]}</div></article>`).join('')}
    </div>
    <section class="panel"><div class="panel-head"><h2>Runtime configuration</h2></div>
      <div class="status-line">
        <span class="status-chip"><b>Embedding</b> ${esc(config.embedding.provider)} / ${esc(config.embedding.model)}</span>
        <span class="status-chip"><b>Dimensions</b> ${config.embedding.dimensions}</span>
        <span class="status-chip"><b>Cache</b> ${esc(config.cache.backend)}</span>
        <span class="status-chip"><b>Observability</b> ${config.observability.enabled?'enabled':'disabled'}</span>
      </div>
    </section>
    <section class="panel"><div class="panel-head"><h2>Cache snapshot</h2></div><div class="pre">${esc(JSON.stringify(overview.cache,null,2))}</div></section>`;
}

async function definitions(kind){
  const items=await api('/v1/'+kind);state[kind]=items;
  const isAgent=kind==='agents';
  content.innerHTML=`<section class="panel"><div class="panel-head"><div><h2>${isAgent?'Agent definitions':'Skill definitions'}</h2><div class="muted">Persistent, versioned platform configuration.</div></div></div>
    <div class="split"><div class="list" id="definition-list"></div><div><textarea id="definition-editor" class="editor"></textarea><div class="toolbar" style="margin-top:10px"><button class="primary" id="save-definition">Save changes</button></div></div></div></section>`;
  const list=document.querySelector('#definition-list'),editor=document.querySelector('#definition-editor');
  items.forEach((item,index)=>{const b=document.createElement('button');b.innerHTML='<strong>'+esc(item.name)+'</strong><br><span class="muted mono">'+esc(item.key)+' · v'+item.version+'</span>';b.onclick=()=>{state.selected=item;editor.value=JSON.stringify(item,null,2);document.querySelectorAll('#definition-list button').forEach(x=>x.classList.remove('active'));b.classList.add('active')};list.appendChild(b);if(index===0)b.click()});
  if(!items.length)list.innerHTML='<div class="empty">No definitions found.</div>';
  document.querySelector('#save-definition').onclick=async()=>{if(!state.selected)return;const body=JSON.parse(editor.value);const saved=await api('/v1/'+kind+'/'+encodeURIComponent(state.selected.key),{method:'PUT',body:JSON.stringify(body)});editor.value=JSON.stringify(saved,null,2);toast('Saved')};
}

async function knowledge(){
  const bases=await api('/v1/knowledge-bases');state.bases=bases;
  content.innerHTML=`<section class="panel"><div class="panel-head"><div><h2>Knowledge bases</h2><div class="muted">Browse documents and upload reference material.</div></div></div>
    <div class="split"><div class="list" id="base-list"></div><div id="documents"><div class="empty">Select a knowledge base.</div></div></div></section>`;
  const list=document.querySelector('#base-list');
  bases.forEach(base=>{const b=document.createElement('button');b.innerHTML='<strong>'+esc(base.name)+'</strong><br><span class="mono muted">'+esc(base.key)+'</span>';b.onclick=()=>loadDocuments(base,b);list.appendChild(b)});
}
async function loadDocuments(base,button){
  document.querySelectorAll('#base-list button').forEach(x=>x.classList.remove('active'));button.classList.add('active');
  const docs=await api('/v1/knowledge-bases/'+encodeURIComponent(base.key)+'/documents');
  document.querySelector('#documents').innerHTML=`<div class="panel-head"><h2>${esc(base.name)}</h2><label class="small-btn">Upload file<input id="file-upload" type="file" hidden></label></div>
  <div class="table-wrap"><table><thead><tr><th>Title</th><th>Status</th><th>Type</th><th>Created</th></tr></thead><tbody>${docs.map(d=>`<tr><td><strong>${esc(d.title)}</strong><br><span class="mono muted">${esc(d.id)}</span></td><td><span class="pill ${d.status==='READY'?'on':''}">${esc(d.status)}</span></td><td>${esc(d.media_type)}</td><td>${new Date(d.created_at).toLocaleString()}</td></tr>`).join('')}</tbody></table></div>`;
  document.querySelector('#file-upload').onchange=async e=>{const file=e.target.files[0];if(!file)return;const data=new FormData();data.append('file',file);const res=await fetch('/v1/knowledge-bases/'+encodeURIComponent(base.key)+'/files',{method:'POST',body:data});if(!res.ok)throw new Error(await res.text());toast('Uploaded and ingested');await loadDocuments(base,button)};
}

async function ontology(){
  const [concepts,relationships]=await Promise.all([api('/v1/ontology/concepts'),api('/v1/ontology/relationships')]);state.concepts=concepts;state.relationships=relationships;
  content.innerHTML=`<div class="grid" style="grid-template-columns:1fr 1fr">
    <section class="panel"><div class="panel-head"><h2>Concepts</h2></div>
      <div class="form two"><label>Key<input id="concept-key" placeholder="technology.openshift"></label><label>Name<input id="concept-name" placeholder="OpenShift"></label><label>Type<input id="concept-type" placeholder="technology"></label><label>Aliases<input id="concept-aliases" placeholder="OCP, Red Hat OpenShift"></label><label class="wide">Description<textarea id="concept-description"></textarea></label></div>
      <div class="toolbar" style="margin:10px 0 14px"><button class="primary" id="create-concept">Create concept</button></div>
      <div class="table-wrap"><table><thead><tr><th>Concept</th><th>Type</th><th></th></tr></thead><tbody>${concepts.map(c=>`<tr><td><strong>${esc(c.name)}</strong><br><span class="mono muted">${esc(c.key)}</span></td><td>${esc(c.type)}</td><td><button class="danger" data-delete-concept="${esc(c.key)}">Delete</button></td></tr>`).join('')}</tbody></table></div>
    </section>
    <section class="panel"><div class="panel-head"><h2>Relationships</h2></div>
      <div class="form"><label>Source<select id="rel-source">${concepts.map(c=>`<option value="${esc(c.key)}">${esc(c.name)}</option>`).join('')}</select></label><label>Relation<input id="rel-type" value="RELATED_TO"></label><label>Target<select id="rel-target">${concepts.map(c=>`<option value="${esc(c.key)}">${esc(c.name)}</option>`).join('')}</select></label></div>
      <div class="toolbar" style="margin:10px 0 14px"><button class="primary" id="create-rel">Create relationship</button></div>
      <div class="table-wrap"><table><thead><tr><th>Source</th><th>Relation</th><th>Target</th><th></th></tr></thead><tbody>${relationships.map(r=>`<tr><td class="mono">${esc(r.source_key)}</td><td>${esc(r.relation)}</td><td class="mono">${esc(r.target_key)}</td><td><button class="danger" data-delete-rel="${r.id}">Delete</button></td></tr>`).join('')}</tbody></table></div>
    </section></div>`;
  document.querySelector('#create-concept').onclick=async()=>{await api('/v1/ontology/concepts',{method:'POST',body:JSON.stringify({key:val('concept-key'),name:val('concept-name'),type:val('concept-type'),description:val('concept-description'),aliases:val('concept-aliases').split(',').map(x=>x.trim()).filter(Boolean),metadata:{},enabled:true})});toast('Concept created');openSection('ontology')};
  document.querySelector('#create-rel').onclick=async()=>{await api('/v1/ontology/relationships',{method:'POST',body:JSON.stringify({source_key:val('rel-source'),relation:val('rel-type').trim().toUpperCase(),target_key:val('rel-target'),metadata:{}})});toast('Relationship created');openSection('ontology')};
  document.querySelectorAll('[data-delete-concept]').forEach(b=>b.onclick=async()=>{await api('/v1/ontology/concepts/'+encodeURIComponent(b.dataset.deleteConcept),{method:'DELETE'});toast('Concept deleted');openSection('ontology')});
  document.querySelectorAll('[data-delete-rel]').forEach(b=>b.onclick=async()=>{await api('/v1/ontology/relationships/'+b.dataset.deleteRel,{method:'DELETE'});toast('Relationship deleted');openSection('ontology')});
}

async function memory(){
  content.innerHTML=`<section class="panel"><div class="panel-head"><div><h2>Memory recall</h2><div class="muted">Inspect memory by explicit scope. Global enumeration is intentionally not exposed.</div></div></div>
    <div class="form two"><label>Scope type<select id="memory-type"><option>correlation</option><option>agent</option><option>global</option><option>custom</option></select></label><label>Scope key<input id="memory-key" placeholder="UUID, agent key, * or custom key"></label><label>Limit<input id="memory-limit" type="number" value="20"></label></div>
    <div class="toolbar" style="margin:10px 0"><button class="primary" id="recall-memory">Recall</button></div><div id="memory-results"></div></section>`;
  document.querySelector('#recall-memory').onclick=async()=>{const items=await api('/v1/memory/recall',{method:'POST',body:JSON.stringify({scopes:[{type:val('memory-type'),key:val('memory-key')}],kinds:[],min_importance:0,limit:Number(val('memory-limit')||20)})});document.querySelector('#memory-results').innerHTML=items.length?items.map(m=>`<div class="pre" style="margin-bottom:8px"><strong>${esc(m.kind)}</strong> · ${esc(m.id)}\n${esc(m.content)}</div>`).join(''):'<div class="empty">No memories found.</div>'};
}

async function tools(){
  const [servers,tools]=await Promise.all([api('/v1/mcp/servers'),api('/v1/tools?refresh=true').catch(e=>({error:e.message}))]);
  content.innerHTML=`<section class="panel"><div class="panel-head"><h2>MCP servers</h2></div><div class="table-wrap"><table><thead><tr><th>Key</th><th>Command</th><th>Status</th></tr></thead><tbody>${servers.map(s=>`<tr><td class="mono">${esc(s.key)}</td><td class="mono">${esc(s.command+' '+s.args.join(' '))}</td><td><span class="pill ${s.enabled?'on':''}">${s.enabled?'enabled':'disabled'}</span></td></tr>`).join('')}</tbody></table></div></section>
  <section class="panel"><div class="panel-head"><h2>Discovered tools</h2></div>${Array.isArray(tools)?`<div class="table-wrap"><table><thead><tr><th>Tool</th><th>Provider</th><th>Description</th></tr></thead><tbody>${tools.map(t=>`<tr><td class="mono">${esc(t.key)}</td><td>${esc(t.provider)}</td><td>${esc(t.description)}</td></tr>`).join('')}</tbody></table></div>`:`<div class="pre">${esc(tools.error)}</div>`}</section>`;
}

async function cache(){
  const stats=await api('/v1/cache/stats');const names=Object.keys(stats.namespaces);
  content.innerHTML=`<section class="panel"><div class="panel-head"><h2>Cache namespaces</h2></div><div class="table-wrap"><table><thead><tr><th>Namespace</th><th>Hits</th><th>Misses</th><th>Writes</th><th>Invalidations</th><th></th></tr></thead><tbody>${names.map(n=>{const s=stats.namespaces[n];return`<tr><td class="mono">${esc(n)}</td><td>${s.hits}</td><td>${s.misses}</td><td>${s.writes}</td><td>${s.invalidations}</td><td><button class="danger" data-cache="${esc(n)}">Invalidate</button></td></tr>`}).join('')}</tbody></table></div></section>`;
  document.querySelectorAll('[data-cache]').forEach(b=>b.onclick=async()=>{await api('/v1/cache/'+encodeURIComponent(b.dataset.cache),{method:'DELETE'});toast('Cache invalidated');openSection('cache')});
}

async function observability(){
  const config=await api('/v1/admin/config');
  content.innerHTML=`<section class="panel"><div class="panel-head"><div><h2>Observability</h2><div class="muted">OpenTelemetry tracing, Prometheus metrics and execution diagnostics.</div></div></div>
    <div class="status-line"><span class="status-chip"><b>OTel</b> ${config.observability.enabled?'enabled':'disabled'}</span><span class="status-chip"><b>Endpoint</b> ${esc(config.observability.otlp_endpoint)}</span></div>
    <div class="toolbar" style="margin-top:14px"><a class="primary" href="/metrics" target="_blank">Prometheus metrics ↗</a><a class="secondary" href="${esc(config.observability.jaeger_url)}" target="_blank">Jaeger ↗</a></div></section>
    <section class="panel"><div class="panel-head"><h2>Execution diagnostics</h2></div><div class="toolbar"><input id="execution-id" placeholder="Execution UUID"><button class="primary" id="load-diagnostics">Load diagnostics</button></div><div id="diagnostics" style="margin-top:12px"></div></section>`;
  document.querySelector('#load-diagnostics').onclick=async()=>{const d=await api('/v1/executions/'+encodeURIComponent(val('execution-id'))+'/diagnostics');document.querySelector('#diagnostics').innerHTML='<div class="pre">'+esc(JSON.stringify(d,null,2))+'</div>'};
}
function val(id){return document.querySelector('#'+id)?.value||''}

checkHealth();openSection('dashboard');
