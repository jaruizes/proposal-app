import { Injectable, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { AgentExecutionTelemetry, OfferExecution, SectionConfig } from './models';
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
  private events = new Map<string, EventSource>();
  private agentPollers = new Map<string, ReturnType<typeof setInterval>>();
  constructor(private http: HttpClient) { this.refresh(); }

  refresh() {
    this.http.get<OfferExecution[]>('/api/offers').subscribe(items =>
      this.executions.set([...items].sort((a,b)=>new Date(b.createdAt).getTime()-new Date(a.createdAt).getTime()))
    );
  }

  create(data: any) {
    const request = { name:data.name, customer:data.customer || data.name.split('·')[0].trim(), language:'es', presentationLanguage:data.presentationLanguage==='English'?'en':'es', inputDriveFolder:data.inputDriveFolder, outputDriveFolder:data.outputDriveFolder, presentationName:data.presentationName, presentationTemplateId:data.presentationTemplateId, aiProvider:data.provider, models:{ analysis:data.models.analysis, strategy:data.models.strategy, solutionArchitecture:data.models.solution, deliveryPlanning:data.models.solution, slidePlanning:data.models.slides, presentation:data.models.slides }, presentationGuidance:{ sections:data.sections.filter((s:SectionConfig)=>s.enabled) } };
    this.http.post<OfferExecution>('/api/offers',request).subscribe(offer=>{this.executions.update(items=>[offer,...items.filter(i=>i.id!==offer.id)]);this.watch(offer.id);this.watchAgents(offer.id);});
  }

  get(id:string){return this.executions().find(e=>e.id===id);}
  approve(id:string,phaseKey:string){this.http.post<void>(`/api/offers/${id}/phases/${phaseKey}/approve`,{}).subscribe(()=>this.refreshOne(id));}
  updateConfiguration(id:string,data:any){return this.http.put<OfferExecution>(`/api/offers/${id}/configuration`,data);}
  retry(id:string,phaseKey:string){this.http.post<void>(`/api/offers/${id}/phases/${phaseKey}/retry`,{}).subscribe(()=>{this.refreshOne(id);this.refreshAgents(id);});}
  refine(id:string,phaseKey:string,message:string){this.http.post<void>(`/api/offers/${id}/phases/${phaseKey}/refine`,{instruction:message}).subscribe(()=>{this.refreshOne(id);this.refreshAgents(id);});}

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
