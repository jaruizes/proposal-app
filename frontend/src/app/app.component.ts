import { CommonModule } from '@angular/common';
import { Component, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ExecutionService } from './execution.service';
import { KnowledgeComponent } from './knowledge.component';
import { AgentExecutionTelemetry, OfferExecution, Phase, ProposalSectionConfig, SectionConfig } from './models';

type PhaseArtifact={type:string;version:number;title:string;content:string};

@Component({selector:'app-root',standalone:true,imports:[CommonModule,FormsModule,KnowledgeComponent],templateUrl:'./app.component.html'})
export class AppComponent {
  svc=inject(ExecutionService); view=signal<'home'|'detail'|'knowledge'>('home'); selectedId=signal<string|null>(null); selectedPhaseKey=signal<string|null>(null); selectedArtifactIndex=signal(0); createOpen=signal(false); configOpen=signal(false); showRawMarkdown=signal(false); chatMessage='';
  providerModels:Record<string,string[]>={ANTHROPIC:['claude-sonnet-4-6','claude-opus-4-6'],'AWS Bedrock':['claude-sonnet-4-6'],OpenAI:['gpt-5.6']};
  draft:any=this.newDraft(); configDraft:any={}; selected=computed(()=>this.selectedId()?this.svc.get(this.selectedId()!):undefined); selectedPhase=computed(()=>this.selected()?.phases.find(p=>p.key===this.selectedPhaseKey()));
  selectedArtifacts=computed(()=>this.phaseArtifacts(this.selectedPhase()));
  selectedArtifact=computed(()=>this.selectedArtifacts()[this.selectedArtifactIndex()]||this.selectedArtifacts()[0]);
  stats=computed(()=>{const items=this.svc.executions();return{total:items.length,working:items.filter(x=>x.overallStatus==='Trabajando').length,waiting:items.filter(x=>x.overallStatus==='Esperando aprobación').length};});
  agentStats=computed(()=>{const items=this.svc.agentExecutions();return{running:items.filter(x=>x.status==='RUNNING').length,failed:items.filter(x=>x.status==='FAILED').length,input:items.reduce((sum,x)=>sum+(x.inputTokens||0),0),output:items.reduce((sum,x)=>sum+(x.outputTokens||0),0)};});
  latestFailedAgent=computed(()=>this.svc.agentExecutions().find(x=>x.status==='FAILED'));
  failedPhase=computed(()=>this.selected()?.phases.find(p=>p.status==='failed'));
  offerErrorMessage=computed(()=>this.latestFailedAgent()?.errorMessage||this.failedPhase()?.errorMessage||'');
  openCreate(){this.draft=this.newDraft();this.createOpen.set(true);} closeCreate(){this.createOpen.set(false);} saveCreate(){this.svc.create(this.draft);this.createOpen.set(false);}
  openConfig(){const e=this.selected();if(!e)return;this.configDraft={presentationLanguage:e.presentationLanguage,inputDriveFolder:e.inputDriveFolder,outputDriveFolder:e.outputDriveFolder,presentationName:e.presentationName,presentationTemplateId:e.presentationTemplateId||'',proposalTemplateId:e.proposalTemplateId||'builtin-neutral',aiProvider:e.provider,models:{...e.models},proposalGuidance:structuredClone(e.proposalGuidance||{sections:this.svc.defaultProposalSections}),presentationGuidance:e.sections};this.configOpen.set(true);}
  closeConfig(){this.configOpen.set(false);}
  saveConfig(){const e=this.selected();if(!e)return;this.svc.updateConfiguration(e.id,this.configDraft).subscribe(updated=>{this.svc.executions.update(items=>items.map(x=>x.id===updated.id?updated:x));this.configOpen.set(false);});}
  retryFailedPhase(){const e=this.selected(),p=this.failedPhase();if(e&&p)this.svc.retry(e.id,p.key);}
  openDetail(exec:OfferExecution){this.selectedId.set(exec.id);this.view.set('detail');this.svc.watch(exec.id);this.svc.watchAgents(exec.id);const candidate=exec.phases.find(p=>p.status==='waiting_approval')||exec.phases.find(p=>p.status==='approved');this.selectedPhaseKey.set(candidate?.key||null);this.resetArtifactView();}
  openKnowledge(){const id=this.selectedId();if(id)this.svc.stopWatchingAgents(id);this.selectedId.set(null);this.selectedPhaseKey.set(null);this.view.set('knowledge');}
  openHome(){const id=this.selectedId();if(id)this.svc.stopWatchingAgents(id);this.selectedId.set(null);this.selectedPhaseKey.set(null);this.view.set('home');}
  back(){const id=this.selectedId();if(id)this.svc.stopWatchingAgents(id);this.view.set('home');this.selectedId.set(null);this.selectedPhaseKey.set(null);this.resetArtifactView();} phaseClickable(p:Phase){return p.status==='approved'||p.status==='waiting_approval';} choosePhase(p:Phase){if(this.phaseClickable(p)){this.selectedPhaseKey.set(p.key);this.resetArtifactView();}}
  chooseArtifact(index:number){this.selectedArtifactIndex.set(index);this.showRawMarkdown.set(false);}
  approve(){const e=this.selected(),p=this.selectedPhase();if(e&&p){this.svc.approve(e.id,p.key);this.selectedPhaseKey.set(null);this.resetArtifactView();}}
  sendRefine(){const e=this.selected(),p=this.selectedPhase();if(e&&p&&this.chatMessage.trim()){this.svc.refine(e.id,p.key,this.chatMessage.trim());this.chatMessage='';}}
  statusClass(status:string){return status==='Trabajando'?'working':status==='Esperando aprobación'?'waiting':status==='Completado'?'approved':'cancelled';} phaseClass(status:string){return status.replace('_','-');} currentModels(){return this.providerModels[this.draft.provider]||[];} addSection(){this.draft.sections.push({name:'Nueva sección',maxSlides:3,enabled:true});} removeSection(i:number){this.draft.sections.splice(i,1);} addProposalSection(target:'draft'|'config'='draft'){const section:ProposalSectionConfig={name:'Nueva sección',enabled:true,depth:'STANDARD',guidance:''};if(target==='draft')this.draft.proposalSections.push(section);else{this.configDraft.proposalGuidance=this.configDraft.proposalGuidance||{sections:[]};this.configDraft.proposalGuidance.sections.push(section);}} removeProposalSection(i:number,target:'draft'|'config'='draft'){if(target==='draft')this.draft.proposalSections.splice(i,1);else this.configDraft.proposalGuidance.sections.splice(i,1);}
  agentStatusClass(status:string){return status==='RUNNING'?'running':status==='COMPLETED'?'completed':status==='FAILED'?'failed':'pending';}
  agentStatusLabel(status:string){return status==='RUNNING'?'Trabajando':status==='COMPLETED'?'Completado':status==='FAILED'?'Error':status;}
  agentDuration(agent:AgentExecutionTelemetry){const start=agent.startedAt?new Date(agent.startedAt).getTime():0;if(!start)return '—';const end=agent.completedAt?new Date(agent.completedAt).getTime():Date.now();const seconds=Math.max(0,Math.round((end-start)/1000));return seconds<60?`${seconds}s`:`${Math.floor(seconds/60)}m ${seconds%60}s`;}
  agentPhaseLabel(phase:string){const labels:Record<string,string>={ANALYSIS:'Análisis',STRATEGY:'Estrategia',SOLUTION:'Solución',PROPOSAL:'Oferta detallada',SLIDE_PLAN:'Plan narrativo',PRESENTATION:'Presentación'};return labels[phase]||phase;}
  formatTokens(value:number){return new Intl.NumberFormat('es-ES').format(value||0);}
  friendlyErrorCause(raw:string|undefined):string {
    if(!raw?.trim())return 'Se produjo un error inesperado durante la ejecución del agente.';
    const value=raw.toLowerCase();
    if(/max[_ -]?tokens|token limit|too many tokens|context window|context length|maximum.*token/.test(value)) return 'se alcanzó el límite máximo de tokens permitido para esta ejecución.';
    if(/timeout|timed out|readtimeout|apitimeouterror/.test(value)) return 'la generación superó el tiempo máximo permitido.';
    if(/rate.?limit|too many requests|\\b429\\b|overload/.test(value)) return 'el proveedor de IA está temporalmente saturado y no pudo atender la solicitud.';
    if(/connection|network|dns|connection reset|connection refused|broken pipe|unreachable/.test(value)) return 'se produjo un problema de red al comunicarse con un servicio necesario.';
    if(/nats|jetstream|command.*error|message.*ack/.test(value)) return 'se produjo un problema en la comunicación interna con la plataforma de agentes.';
    if(/knowledge|retriev|vector|embedding/.test(value)) return 'no se pudo recuperar correctamente la información necesaria de la base de conocimiento.';
    if(/tool|mcp|google workspace/.test(value)) return 'no se pudo acceder a una herramienta externa necesaria para completar la tarea.';
    if(/validat|schema|format|parse|invalid json/.test(value)) return 'la respuesta generada no cumplía el formato esperado para esta fase.';
    if(/auth|unauthor|forbidden|api.?key|\\b401\\b|\\b403\\b/.test(value)) return 'no se pudo autenticar correctamente contra uno de los servicios necesarios.';
    return 'se produjo un error inesperado durante la ejecución del agente.';
  }
  friendlyAgentError(agent:AgentExecutionTelemetry):string {
    const objective=(agent.objective||'ejecutar la fase '+this.agentPhaseLabel(agent.phase).toLowerCase()).trim();
    const readable=objective.charAt(0).toLowerCase()+objective.slice(1);
    return 'El agente encargado de '+readable+' terminó con error: '+this.friendlyErrorCause(agent.errorMessage);
  }
  offerErrorTitle():string {
    const phase=this.failedPhase();
    return phase?'No se pudo completar la fase "'+phase.label+'".':'No se pudo completar la ejecución de la oferta.';
  }
  offerFriendlyError():string {
    const agent=this.latestFailedAgent();
    return agent?this.friendlyAgentError(agent):'La fase no pudo completarse: '+this.friendlyErrorCause(this.offerErrorMessage());
  }

  phaseArtifacts(phase:Phase|undefined):PhaseArtifact[]{
    const output=phase?.output?.trim();
    if(!output)return [];
    const marker=/^#\s+([A-Z][A-Z0-9_]*)\s+·\s+v(\d+)\s*$/gm;
    const matches=[...output.matchAll(marker)];
    if(!matches.length)return [{type:'DOCUMENT',version:1,title:phase?.label||'Documento',content:output}];
    return matches.map((match,index)=>{
      const start=(match.index||0)+match[0].length;
      const end=index+1<matches.length?(matches[index+1].index||output.length):output.length;
      const type=match[1]; const version=Number(match[2]);
      return {type,version,title:this.artifactLabel(type),content:output.slice(start,end).trim()};
    });
  }

  renderMarkdown(markdown:string|undefined):string {
    if (!markdown) return '<p>El artefacto todavía no está disponible.</p>';
    const lines=markdown.replace(/\r\n/g,'\n').split('\n');
    const html:string[]=[];
    let inCode=false; let code:string[]=[]; let listType:''|'ul'|'ol'='';
    const closeList=()=>{if(listType){html.push(`</${listType}>`);listType='';}};
    for(let i=0;i<lines.length;i++){
      const line=lines[i];
      if(line.trim().startsWith('```')){closeList();if(inCode){html.push(`<pre><code>${this.escapeHtml(code.join('\n'))}</code></pre>`);code=[];}inCode=!inCode;continue;}
      if(inCode){code.push(line);continue;}
      if(this.isTableHeader(lines,i)){
        closeList(); const headers=this.tableCells(line); i+=2; const rows:string[][]=[];
        while(i<lines.length&&this.isTableRow(lines[i])){rows.push(this.tableCells(lines[i]));i++;}
        i--;
        html.push('<div style="overflow-x:auto"><table style="width:100%;border-collapse:collapse;margin:1rem 0"><thead><tr>'+headers.map(h=>`<th style="text-align:left;border:1px solid #29324a;padding:.6rem">${this.inlineMarkdown(h)}</th>`).join('')+'</tr></thead><tbody>'+rows.map(r=>'<tr>'+r.map(c=>`<td style="vertical-align:top;border:1px solid #29324a;padding:.6rem">${this.inlineMarkdown(c)}</td>`).join('')+'</tr>').join('')+'</tbody></table></div>');
        continue;
      }
      const heading=line.match(/^(#{1,6})\s+(.+)$/); if(heading){closeList();const level=heading[1].length;html.push(`<h${level} style="margin:1.4rem 0 .7rem">${this.inlineMarkdown(heading[2])}</h${level}>`);continue;}
      const bullet=line.match(/^\s*[-*+]\s+(.+)$/); if(bullet){if(listType!=='ul'){closeList();listType='ul';html.push('<ul>');}html.push(`<li>${this.inlineMarkdown(bullet[1])}</li>`);continue;}
      const ordered=line.match(/^\s*\d+[.)]\s+(.+)$/); if(ordered){if(listType!=='ol'){closeList();listType='ol';html.push('<ol>');}html.push(`<li>${this.inlineMarkdown(ordered[1])}</li>`);continue;}
      closeList(); if(!line.trim()){html.push('<div style="height:.45rem"></div>');continue;}
      html.push(`<p style="margin:.45rem 0;line-height:1.65">${this.inlineMarkdown(line)}</p>`);
    }
    closeList(); if(inCode)html.push(`<pre><code>${this.escapeHtml(code.join('\n'))}</code></pre>`);
    return html.join('');
  }
  private resetArtifactView(){this.selectedArtifactIndex.set(0);this.showRawMarkdown.set(false);}
  private artifactLabel(type:string){return type.toLowerCase().split('_').map(word=>word.charAt(0).toUpperCase()+word.slice(1)).join(' ');}
  private isTableHeader(lines:string[],i:number){return i+1<lines.length&&this.isTableRow(lines[i])&&/^\s*\|?\s*:?-{3,}/.test(lines[i+1])&&lines[i+1].includes('|');}
  private isTableRow(line:string){return line.includes('|')&&line.trim().length>0;}
  private tableCells(line:string){return line.trim().replace(/^\|/,'').replace(/\|$/,'').split('|').map(x=>x.trim());}
  private inlineMarkdown(value:string){let s=this.escapeHtml(value);s=s.replace(/`([^`]+)`/g,'<code>$1</code>').replace(/\*\*([^*]+)\*\*/g,'<strong>$1</strong>').replace(/__([^_]+)__/g,'<strong>$1</strong>').replace(/\*([^*]+)\*/g,'<em>$1</em>');return s;}
  private escapeHtml(value:string){return value.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#039;');}
  private newDraft(){return{name:'',customer:'',presentationLanguage:'Español',inputDriveFolder:'',outputDriveFolder:'',presentationName:'',presentationTemplateId:'',proposalTemplateId:'builtin-neutral',provider:'ANTHROPIC',models:{analysis:'claude-sonnet-4-6',strategy:'claude-sonnet-4-6',solution:'claude-sonnet-4-6',proposal:'claude-sonnet-4-6',slides:'claude-sonnet-4-6'},proposalSections:structuredClone(this.svc.defaultProposalSections) as ProposalSectionConfig[],sections:structuredClone(this.svc.defaultSections) as SectionConfig[]};}
}
