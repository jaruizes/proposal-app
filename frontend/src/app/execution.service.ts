import { Injectable, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { AgentExecutionTelemetry, OfferExecution, ProposalSectionConfig, SectionConfig } from './models';
@Injectable({ providedIn: 'root' })
export class ExecutionService {
  executions = signal<OfferExecution[]>([]);
  agentExecutions = signal<AgentExecutionTelemetry[]>([]);
  readonly defaultSections: SectionConfig[] = [
    { name: 'Resumen ejecutivo', maxSlides: 3, enabled: true },
    { name: 'Introducción, contexto y objetivos', maxSlides: 5, enabled: true },
    { name: 'Alcance y consideraciones', maxSlides: 5, enabled: true },
    { name: '¿Qué proponemos?', maxSlides: 10, enabled: true },
    { name: '¿Cómo lo vamos a hacer?', maxSlides: 10, enabled: true }
  ];
  readonly defaultProposalSections: ProposalSectionConfig[] = [
    { name:'Resumen ejecutivo', enabled:true, depth:'SUMMARY', guidance:'Sintetizar reto, propuesta de valor y resultados esperados.' },
    { name:'Entendimiento del reto', enabled:true, depth:'STANDARD', guidance:'Explicar contexto, necesidades y condicionantes sin inventar hechos.' },
    { name:'Objetivos y alcance', enabled:true, depth:'STANDARD', guidance:'Cubrir objetivos, alcance, exclusiones y dependencias conocidas.' },
    { name:'Requisitos y condicionantes', enabled:true, depth:'DETAILED', guidance:'Responder a requisitos funcionales, no funcionales y restricciones relevantes.' },
    { name:'Estrategia de respuesta', enabled:true, depth:'STANDARD', guidance:'Conectar necesidades con la estrategia aprobada.' },
    { name:'Solución propuesta', enabled:true, depth:'DETAILED', guidance:'Describir la solución funcional y técnica con suficiente profundidad.' },
    { name:'Arquitectura e integraciones', enabled:true, depth:'DETAILED', guidance:'Detallar arquitectura, componentes, datos, integraciones, seguridad y operación cuando aplique.' },
    { name:'Enfoque de ejecución', enabled:true, depth:'DETAILED', guidance:'Describir fases, workstreams, entregables, gobierno y dependencias sin inventar estimaciones.' },
    { name:'Calidad, riesgos y supuestos', enabled:true, depth:'STANDARD', guidance:'Explicitar calidad, riesgos, mitigaciones, supuestos y cuestiones pendientes.' },
    { name:'Valor añadido y próximos pasos', enabled:true, depth:'STANDARD', guidance:'Resumir diferenciadores sustentados y siguientes pasos.' }
  ];
  private events = new Map<string, EventSource>();
  private agentPollers = new Map<string, ReturnType<typeof setInterval>>();
  constructor(private http: HttpClient) { this.refresh(); }

  refresh() {
    this.http.get<OfferExecution[]>('/api/offers').subscribe(items =>
      this.executions.set([...items].sort((a,b)=>new Date(b.createdAt).getTime()-new Date(a.createdAt).getTime()))
    );
  }

  create(data: any) {
    const request = { name:data.name, customer:data.customer || data.name.split('·')[0].trim(), language:'es', presentationLanguage:data.presentationLanguage==='English'?'en':'es', inputDriveFolder:data.inputDriveFolder, outputDriveFolder:data.outputDriveFolder, presentationName:data.presentationName, presentationTemplateId:data.presentationTemplateId, proposalTemplateId:data.proposalTemplateId || '', aiProvider:data.provider, models:{ analysis:data.models.analysis, strategy:data.models.strategy, solutionArchitecture:data.models.solution, deliveryPlanning:data.models.solution, proposal:data.models.proposal, slidePlanning:data.models.slides, presentation:data.models.slides }, proposalGuidance:{ sections:data.proposalSections.filter((s:ProposalSectionConfig)=>s.enabled) }, presentationGuidance:{ sections:data.sections.filter((s:SectionConfig)=>s.enabled) } };
    this.http.post<OfferExecution>('/api/offers',request).subscribe(offer=>{this.executions.update(items=>[offer,...items.filter(i=>i.id!==offer.id)]);this.watch(offer.id);this.watchAgents(offer.id);});
  }

  get(id:string){return this.executions().find(e=>e.id===id);}
  approve(id:string,phaseKey:string){this.http.post<void>(`/api/offers/${id}/phases/${phaseKey}/approve`,{}).subscribe(()=>this.refreshOne(id));}
  updateConfiguration(id:string,data:any){return this.http.put<OfferExecution>(`/api/offers/${id}/configuration`,data);}
  retry(id:string,phaseKey:string){this.http.post<void>(`/api/offers/${id}/phases/${phaseKey}/retry`,{}).subscribe(()=>{this.refreshOne(id);this.refreshAgents(id);});}
  refine(id:string,phaseKey:string,message:string){this.http.post<void>(`/api/offers/${id}/phases/${phaseKey}/refine`,{instruction:message}).subscribe(()=>{this.refreshOne(id);this.refreshAgents(id);});}

  exportArtifactPdf(offerId:string,type:string,version:number,fileName:string){
    this.http.get(`/api/offers/${offerId}/artifacts/${type}/${version}/pdf`,{responseType:'blob'}).subscribe(blob=>{
      const url=URL.createObjectURL(blob);
      const anchor=document.createElement('a');
      anchor.href=url;
      anchor.download=fileName.replace(/\.md$/i,'')+'.pdf';
      anchor.click();
      URL.revokeObjectURL(url);
    });
  }

  watch(id:string){
    if(this.events.has(id))return;
    const source=new EventSource(`/api/offers/${id}/events`);
    source.addEventListener('offer',(event:MessageEvent)=>this.upsertInPlace(JSON.parse(event.data) as OfferExecution));
    source.onerror=()=>{source.close();this.events.delete(id);};
    this.events.set(id,source);
  }

  watchAgents(id:string){
    this.refreshAgents(id);
    if(this.agentPollers.has(id))return;
    const poller=setInterval(()=>this.refreshAgents(id),2000);
    this.agentPollers.set(id,poller);
  }

  stopWatchingAgents(id:string){
    const poller=this.agentPollers.get(id);
    if(poller)clearInterval(poller);
    this.agentPollers.delete(id);
    this.agentExecutions.set([]);
  }

  refreshAgents(id:string){
    this.http.get<AgentExecutionTelemetry[]>(`/api/offers/${id}/agents`).subscribe(items=>
      this.agentExecutions.set([...items].sort((a,b)=>new Date(b.startedAt||0).getTime()-new Date(a.startedAt||0).getTime()))
    );
  }

  private refreshOne(id:string){
    this.http.get<OfferExecution>(`/api/offers/${id}`).subscribe(offer=>{this.upsertInPlace(offer);this.watch(id);});
  }

  private upsertInPlace(offer:OfferExecution){
    this.executions.update(items=>{
      const index=items.findIndex(item=>item.id===offer.id);
      if(index<0)return [...items,offer];
      const next=[...items];
      next[index]=offer;
      return next;
    });
  }
}
