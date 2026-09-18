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
  const isAgent=kind==='agents';
  const [items,skills,bases]=await Promise.all([
    api('/v1/'+kind),
    isAgent?api('/v1/skills'):Promise.resolve([]),
    !isAgent?api('/v1/knowledge-bases').catch(()=>[]):Promise.resolve([])
  ]);
  state[kind]=items;state.skills=skills;state.bases=bases;
  content.innerHTML=`<section class="panel">
    <div class="panel-head">
      <div><h2>${isAgent?'Agent definitions':'Skill definitions'}</h2><div class="muted">${isAgent?'Configure behavior, skills, tools and model policy.':'Configure objectives, instructions, knowledge and tools.'}</div></div>
      <span class="pill">${items.length} ${kind}</span>
    </div>
    <div class="split definition-split">
      <div class="list" id="definition-list"></div>
      <div id="definition-detail"><div class="empty">Select a definition.</div></div>
    </div>
  </section>`;
  const list=document.querySelector('#definition-list');
  items.forEach((item,index)=>{
    const b=document.createElement('button');
    b.innerHTML=`<div class="definition-list-title"><strong>${esc(item.name)}</strong><span class="pill ${item.enabled?'on':''}">${item.enabled?'enabled':'disabled'}</span></div><span class="muted mono">${esc(item.key)} · v${item.version}</span>`;
    b.onclick=()=>{state.selected=item;document.querySelectorAll('#definition-list button').forEach(x=>x.classList.remove('active'));b.classList.add('active');renderDefinition(kind,item,skills,bases)};
    list.appendChild(b);if(index===0)b.click();
  });
  if(!items.length)list.innerHTML='<div class="empty">No definitions found.</div>';
}

function renderDefinition(kind,item,skills,bases){
  const isAgent=kind==='agents';
  const detail=document.querySelector('#definition-detail');
  detail.innerHTML=`<div class="definition-tabs">
      <button class="small-btn active" data-def-tab="form">Form</button>
      <button class="small-btn" data-def-tab="raw">Raw JSON</button>
    </div>
    <div id="definition-form-view">${isAgent?agentForm(item,skills):skillForm(item,bases)}</div>
    <div id="definition-raw-view" hidden>
      <textarea id="definition-editor" class="editor">${esc(JSON.stringify(item,null,2))}</textarea>
    </div>
    <div class="definition-actions">
      <span class="muted">ID: <span class="mono">${esc(item.id)}</span> · version ${item.version}</span>
      <button class="primary" id="save-definition">Save changes</button>
    </div>`;
  document.querySelectorAll('[data-def-tab]').forEach(button=>button.onclick=()=>{
    const raw=button.dataset.defTab==='raw';
    document.querySelector('#definition-form-view').hidden=raw;
    document.querySelector('#definition-raw-view').hidden=!raw;
    document.querySelectorAll('[data-def-tab]').forEach(x=>x.classList.toggle('active',x===button));
    if(raw)document.querySelector('#definition-editor').value=JSON.stringify(buildDefinitionFromForm(kind,item),null,2);
  });
  document.querySelector('#save-definition').onclick=async()=>{
    const rawVisible=!document.querySelector('#definition-raw-view').hidden;
    const body=rawVisible?JSON.parse(document.querySelector('#definition-editor').value):buildDefinitionFromForm(kind,item);
    const saved=await api('/v1/'+kind+'/'+encodeURIComponent(item.key),{method:'PUT',body:JSON.stringify(body)});
    state.selected=saved;toast('Saved');
    await openSection(kind);
  };
}

function agentForm(item,skills){
  const policy=item.model_policy||{},constraints=item.constraints||{};
  const selected=new Set(item.skills||[]);
  return `<div class="form two definition-form">
    <label>Name<input id="def-name" value="${esc(item.name)}"></label>
    <label>Key<input value="${esc(item.key)}" disabled></label>
    <label class="wide">Description<textarea id="def-description">${esc(item.description||'')}</textarea></label>
    <label>Enabled<select id="def-enabled"><option value="true" ${item.enabled?'selected':''}>Enabled</option><option value="false" ${!item.enabled?'selected':''}>Disabled</option></select></label>
    <label>Capabilities<input id="def-capabilities" value="${esc((item.capabilities||[]).join(', '))}" placeholder="architecture-design, source-analysis"></label>

    <div class="wide field-group"><div class="field-title">Assigned skills</div><div class="check-grid">
      ${skills.map(skill=>`<label class="check-item"><input type="checkbox" data-agent-skill="${esc(skill.key)}" ${selected.has(skill.key)?'checked':''}><span><strong>${esc(skill.name)}</strong><small class="mono">${esc(skill.key)}</small></span></label>`).join('')||'<span class="muted">No skills available.</span>'}
    </div></div>

    <label>Allowed tools<input id="def-tools" value="${esc((item.allowed_tools||[]).join(', '))}" placeholder="source.read, knowledge.search"></label>
    <label>Knowledge scopes<input id="def-scopes" value="${esc((item.knowledge_scopes||[]).join(', '))}" placeholder="architecture, corporate"></label>

    <div class="wide subsection-title">Model policy</div>
    <label>Preferred model<input id="def-model" value="${esc(policy.preferred_model||'')}" placeholder="claude-sonnet-4-6"></label>
    <label>Fallback models<input id="def-fallback-models" value="${esc((policy.fallback_models||[]).join(', '))}"></label>
    <label>Temperature<input id="def-temperature" type="number" min="0" max="2" step="0.1" value="${policy.temperature??''}"></label>
    <label>Max output tokens<input id="def-max-tokens" type="number" min="1" value="${policy.max_output_tokens??''}"></label>

    <div class="wide subsection-title">Execution constraints</div>
    <label>Max delegations<input id="def-max-delegations" type="number" min="0" value="${constraints.max_delegations??0}"></label>
    <label class="checkbox-label"><input id="def-allow-tools" type="checkbox" ${constraints.allow_tool_calls!==false?'checked':''}> Allow tool calls</label>
    <label class="checkbox-label"><input id="def-allow-web" type="checkbox" ${constraints.allow_web?'checked':''}> Allow web</label>
    <label>Extra constraints (JSON)<textarea id="def-extra" class="code-field">${esc(JSON.stringify(constraints.extra||{},null,2))}</textarea></label>

    <label class="wide">Role / system contract<textarea id="def-role" class="large-text">${esc(item.role||'')}</textarea></label>
  </div>`;
}

function skillForm(item,bases){
  const selectedSources=new Set(item.knowledge_sources||[]);
  return `<div class="form two definition-form">
    <label>Name<input id="def-name" value="${esc(item.name)}"></label>
    <label>Key<input value="${esc(item.key)}" disabled></label>
    <label class="wide">Description<textarea id="def-description">${esc(item.description||'')}</textarea></label>
    <label>Enabled<select id="def-enabled"><option value="true" ${item.enabled?'selected':''}>Enabled</option><option value="false" ${!item.enabled?'selected':''}>Disabled</option></select></label>
    <label>Inputs<input id="def-inputs" value="${esc((item.inputs||[]).join(', '))}" placeholder="workspace, source-manifest"></label>
    <label class="wide">Objective<textarea id="def-objective">${esc(item.objective||'')}</textarea></label>

    <div class="wide field-group"><div class="field-title">Knowledge sources</div><div class="check-grid">
      ${bases.map(base=>`<label class="check-item"><input type="checkbox" data-skill-source="${esc(base.key)}" ${selectedSources.has(base.key)?'checked':''}><span><strong>${esc(base.name)}</strong><small class="mono">${esc(base.key)}</small></span></label>`).join('')||'<span class="muted">No knowledge bases available yet.</span>'}
    </div></div>

    <label class="wide">Allowed tools<input id="def-tools" value="${esc((item.allowed_tools||[]).join(', '))}" placeholder="source.read, knowledge.search"></label>
    <label class="wide">Instructions<textarea id="def-instructions" class="large-text">${esc(item.instructions||'')}</textarea></label>

    <details class="wide advanced-box"><summary>Advanced configuration</summary>
      <div class="form two" style="margin-top:10px">
        <label>Output schema (JSON)<textarea id="def-output-schema" class="code-field">${esc(JSON.stringify(item.output_schema||{},null,2))}</textarea></label>
        <label>Constraints (JSON)<textarea id="def-constraints" class="code-field">${esc(JSON.stringify(item.constraints||{},null,2))}</textarea></label>
      </div>
    </details>
  </div>`;
}

function buildDefinitionFromForm(kind,item){
  const common={...item,name:val('def-name').trim(),description:val('def-description'),enabled:val('def-enabled')==='true'};
  if(kind==='agents'){
    const policy=item.model_policy||{},constraints=item.constraints||{};
    return {...common,
      role:val('def-role'),
      capabilities:csv('def-capabilities'),
      skills:[...document.querySelectorAll('[data-agent-skill]:checked')].map(x=>x.dataset.agentSkill),
      knowledge_scopes:csv('def-scopes'),
      allowed_tools:csv('def-tools'),
      model_policy:{...policy,
        preferred_model:val('def-model').trim()||null,
        fallback_models:csv('def-fallback-models'),
        temperature:numberOrNull('def-temperature'),
        max_output_tokens:intOrNull('def-max-tokens')
      },
      constraints:{...constraints,
        max_delegations:Number(val('def-max-delegations')||0),
        allow_web:document.querySelector('#def-allow-web').checked,
        allow_tool_calls:document.querySelector('#def-allow-tools').checked,
        extra:parseJsonField('def-extra',{})
      }
    };
  }
  return {...common,
    objective:val('def-objective'),
    instructions:val('def-instructions'),
    inputs:csv('def-inputs'),
    knowledge_sources:[...document.querySelectorAll('[data-skill-source]:checked')].map(x=>x.dataset.skillSource),
    allowed_tools:csv('def-tools'),
    output_schema:parseJsonField('def-output-schema',item.output_schema||{}),
    constraints:parseJsonField('def-constraints',item.constraints||{})
  };
}

function csv(id){return val(id).split(',').map(x=>x.trim()).filter(Boolean)}
function numberOrNull(id){const value=val(id).trim();return value===''?null:Number(value)}
function intOrNull(id){const value=val(id).trim();return value===''?null:parseInt(value,10)}
function parseJsonField(id,fallback){const el=document.querySelector('#'+id);if(!el)return fallback;const text=el.value.trim();return text?JSON.parse(text):fallback}

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
  const [concepts,relationships]=await Promise.all([api('/v1/ontology/concepts'),api('/v1/ontology/relationships')]);
  state.concepts=concepts;state.relationships=relationships;
  content.innerHTML=`<div class="grid" style="grid-template-columns:1fr 1fr">
    <section class="panel"><div class="panel-head"><div><h2>Concepts</h2><div class="muted">Create and manage canonical concepts and aliases.</div></div></div>
      <div class="form two">
        <label>Key<input id="concept-key" placeholder="technology.openshift"></label>
        <label>Name<input id="concept-name" placeholder="OpenShift"></label>
        <label>Type<input id="concept-type" placeholder="technology"></label>
        <label>Aliases<input id="concept-aliases" placeholder="OCP, Red Hat OpenShift"></label>
        <label class="wide">Description<textarea id="concept-description" placeholder="Enterprise Kubernetes platform"></textarea></label>
      </div>
      <div class="toolbar" style="margin:10px 0 14px"><button class="primary" id="create-concept">Create concept</button></div>
      <div class="table-wrap"><table><thead><tr><th>Concept</th><th>Type</th><th>Aliases</th><th></th></tr></thead><tbody>
        ${concepts.map(c=>`<tr><td><strong>${esc(c.name)}</strong><br><span class="mono muted">${esc(c.key)}</span></td><td><span class="pill">${esc(c.type)}</span></td><td>${esc((c.aliases||[]).join(', ')||'—')}</td><td><button class="danger" data-delete-concept="${esc(c.key)}">Delete</button></td></tr>`).join('')}
      </tbody></table></div>
    </section>
    <section class="panel"><div class="panel-head"><div><h2>Relationships</h2><div class="muted">Connect concepts for graph-aware retrieval.</div></div></div>
      <div class="form">
        <label>Source<select id="rel-source">${concepts.map(c=>`<option value="${esc(c.key)}">${esc(c.name)} · ${esc(c.key)}</option>`).join('')}</select></label>
        <label>Relation<input id="rel-type" value="RELATED_TO" placeholder="IS_A"></label>
        <label>Target<select id="rel-target">${concepts.map(c=>`<option value="${esc(c.key)}">${esc(c.name)} · ${esc(c.key)}</option>`).join('')}</select></label>
      </div>
      <div class="toolbar" style="margin:10px 0 14px"><button class="primary" id="create-rel" ${concepts.length<2?'disabled':''}>Create relationship</button></div>
      <div class="table-wrap"><table><thead><tr><th>Source</th><th>Relation</th><th>Target</th><th></th></tr></thead><tbody>
        ${relationships.map(r=>`<tr><td class="mono">${esc(r.source_key)}</td><td><span class="pill">${esc(r.relation)}</span></td><td class="mono">${esc(r.target_key)}</td><td><button class="danger" data-delete-rel="${r.id}">Delete</button></td></tr>`).join('')}
      </tbody></table></div>
    </section></div>`;
  document.querySelector('#create-concept').onclick=async()=>{
    await api('/v1/ontology/concepts',{method:'POST',body:JSON.stringify({
      key:val('concept-key').trim(),name:val('concept-name').trim(),type:val('concept-type').trim(),
      description:val('concept-description').trim(),aliases:val('concept-aliases').split(',').map(x=>x.trim()).filter(Boolean),
      metadata:{},enabled:true
    })});
    toast('Concept created');openSection('ontology');
  };
  document.querySelector('#create-rel').onclick=async()=>{
    await api('/v1/ontology/relationships',{method:'POST',body:JSON.stringify({
      source_key:val('rel-source'),relation:val('rel-type').trim().toUpperCase(),target_key:val('rel-target'),metadata:{}
    })});
    toast('Relationship created');openSection('ontology');
  };
  document.querySelectorAll('[data-delete-concept]').forEach(b=>b.onclick=async()=>{
    if(!confirm('Delete concept '+b.dataset.deleteConcept+'?'))return;
    await api('/v1/ontology/concepts/'+encodeURIComponent(b.dataset.deleteConcept),{method:'DELETE'});toast('Concept deleted');openSection('ontology');
  });
  document.querySelectorAll('[data-delete-rel]').forEach(b=>b.onclick=async()=>{
    await api('/v1/ontology/relationships/'+b.dataset.deleteRel,{method:'DELETE'});toast('Relationship deleted');openSection('ontology');
  });
}
async function memory(){content.innerHTML='<section class="panel"><div class="panel-head"><h2>Memory recall</h2></div><div class="toolbar"><select id="memory-type"><option>correlation</option><option>agent</option><option>global</option><option>custom</option></select><input id="memory-key" placeholder="scope key"><button class="primary" id="recall-memory">Recall</button></div><div id="memory-results"></div></section>';document.querySelector('#recall-memory').onclick=async()=>{const items=await api('/v1/memory/recall',{method:'POST',body:JSON.stringify({scopes:[{type:val('memory-type'),key:val('memory-key')}],kinds:[],min_importance:0,limit:20})});document.querySelector('#memory-results').innerHTML='<div class="pre">'+esc(JSON.stringify(items,null,2))+'</div>'}}
async function tools(){
  const [servers,toolItems]=await Promise.all([api('/v1/mcp/servers'),api('/v1/tools?refresh=true').catch(e=>({error:e.message}))]);
  content.innerHTML=`<section class="panel">
    <div class="panel-head"><div><h2>MCP servers</h2><div class="muted">Configured external tool providers.</div></div></div>
    <div class="table-wrap"><table><thead><tr><th>Server</th><th>Command</th><th>Status</th></tr></thead><tbody>
      ${servers.map(s=>`<tr><td><strong>${esc(s.key)}</strong></td><td class="mono">${esc(s.command)} ${esc((s.args||[]).join(' '))}</td><td><span class="pill ${s.enabled?'on':''}">${s.enabled?'enabled':'disabled'}</span></td></tr>`).join('')}
    </tbody></table></div>
  </section>
  <section class="panel">
    <div class="panel-head"><div><h2>Discovered tools</h2><div class="muted">Human-readable view of tools exposed by MCP providers.</div></div><span class="pill">${Array.isArray(toolItems)?toolItems.length:0} tools</span></div>
    ${Array.isArray(toolItems)?`<div class="table-wrap"><table><thead><tr><th>Tool</th><th>Provider</th><th>Description</th><th>Input schema</th></tr></thead><tbody>
      ${toolItems.map(t=>`<tr>
        <td><strong>${esc(t.name||t.key)}</strong><br><span class="mono muted">${esc(t.key)}</span></td>
        <td><span class="pill">${esc(t.provider||'—')}</span></td>
        <td>${esc(t.description||'—')}</td>
        <td><details><summary>View schema</summary><div class="pre" style="margin-top:8px;max-height:240px">${esc(JSON.stringify(t.input_schema||{},null,2))}</div></details></td>
      </tr>`).join('')}
    </tbody></table></div>`:`<div class="pre">${esc(toolItems.error||'Tool discovery failed')}</div>`}
  </section>`;
}
async function cache(){const stats=await api('/v1/cache/stats');content.innerHTML='<section class="panel"><div class="panel-head"><h2>Cache</h2></div><div class="pre">'+esc(JSON.stringify(stats,null,2))+'</div></section>'}
async function observability(){const config=await api('/v1/admin/config');content.innerHTML='<section class="panel"><div class="panel-head"><h2>Observability</h2></div><div class="status-line"><span class="status-chip"><b>OTel</b> '+(config.observability.enabled?'enabled':'disabled')+'</span></div><div class="toolbar" style="margin-top:14px"><a class="primary" href="/metrics" target="_blank">Metrics ↗</a><a class="secondary" href="'+esc(config.observability.jaeger_url)+'" target="_blank">Jaeger ↗</a></div></section>'}
function val(id){return document.querySelector('#'+id)?.value||''}
checkHealth();openSection('dashboard');
