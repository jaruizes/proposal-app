import { Injectable, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { OfferExecution, SectionConfig } from './models';
@Injectable({ providedIn: 'root' })
export class ExecutionService {
  executions = signal<OfferExecution[]>([]);
  readonly defaultSections: SectionConfig[] = [
    { name: 'Resumen ejecutivo', maxSlides: 3, enabled: true },
    { name: 'Introducción, contexto y objetivos', maxSlides: 5, enabled: true },
    { name: 'Alcance y consideraciones', maxSlides: 5, enabled: true },
    { name: '¿Qué proponemos?', maxSlides: 10, enabled: true },
    { name: '¿Cómo lo vamos a hacer?', maxSlides: 10, enabled: true }
  ];
  private events = new Map<string, EventSource>();
  constructor(private http: HttpClient) { this.refresh(); }
  refresh() { this.http.get<OfferExecution[]>('/api/offers').subscribe(items => this.executions.set(items)); }
  create(data: any) {
    const request = { name:data.name, customer:data.customer || data.name.split('·')[0].trim(), language:'es', presentationLanguage:data.presentationLanguage==='English'?'en':'es', inputDriveFolder:data.inputDriveFolder, outputDriveFolder:data.outputDriveFolder, presentationName:data.presentationName, aiProvider:data.provider, models:{ analysis:data.models.analysis, strategy:data.models.strategy, solutionArchitecture:data.models.solution, deliveryPlanning:data.models.solution, slidePlanning:data.models.slides, presentation:data.models.slides }, presentationGuidance:{ sections:data.sections.filter((s:SectionConfig)=>s.enabled) } };
    this.http.post<OfferExecution>('/api/offers',request).subscribe(offer=>{this.executions.update(items=>[offer,...items.filter(i=>i.id!==offer.id)]);this.watch(offer.id);});
  }
  get(id:string){return this.executions().find(e=>e.id===id);}
  approve(id:string,phaseKey:string){this.http.post<void>(`/api/offers/${id}/phases/${phaseKey}/approve`,{}).subscribe(()=>this.refreshOne(id));}
  refine(id:string,phaseKey:string,message:string){this.http.post<void>(`/api/offers/${id}/phases/${phaseKey}/refine`,{instruction:message}).subscribe(()=>this.refreshOne(id));}
  watch(id:string){if(this.events.has(id))return;const source=new EventSource(`/api/offers/${id}/events`);source.addEventListener('offer',(event:MessageEvent)=>{const offer=JSON.parse(event.data) as OfferExecution;this.executions.update(items=>[offer,...items.filter(i=>i.id!==offer.id)]);});source.onerror=()=>{source.close();this.events.delete(id);};this.events.set(id,source);}
  private refreshOne(id:string){this.http.get<OfferExecution>(`/api/offers/${id}`).subscribe(offer=>{this.executions.update(items=>[offer,...items.filter(i=>i.id!==id)]);this.watch(id);});}
}
