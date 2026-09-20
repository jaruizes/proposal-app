import { Injectable, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { KnowledgeBase, KnowledgeChunk, KnowledgeDocument, RetrievalResult } from './knowledge.models';

@Injectable({providedIn:'root'})
export class KnowledgeService {
  bases=signal<KnowledgeBase[]>([]);
  documents=signal<KnowledgeDocument[]>([]);
  chunks=signal<KnowledgeChunk[]>([]);
  results=signal<RetrievalResult|null>(null);
  loading=signal(false);
  message=signal('');

  constructor(private http:HttpClient){}

  loadBases(){
    this.http.get<KnowledgeBase[]>('/api/knowledge/bases').subscribe({
      next:items=>{this.bases.set(items);if(!items.length)this.bootstrap();},
      error:()=>this.message.set('No se pudieron cargar las bases de conocimiento.')
    });
  }
  bootstrap(){ this.http.post<KnowledgeBase[]>('/api/knowledge/bases/bootstrap',{}).subscribe(()=>this.loadBases()); }
  loadDocuments(key:string){
    if(!key){this.documents.set([]);return;}
    this.http.get<KnowledgeDocument[]>(`/api/knowledge/bases/${key}/documents`).subscribe({
      next:items=>this.documents.set([...items].sort((a,b)=>new Date(b.created_at).getTime()-new Date(a.created_at).getTime())),
      error:()=>this.message.set('No se pudieron cargar los documentos.')
    });
  }
  loadChunks(id:string){
    this.http.get<KnowledgeChunk[]>(`/api/knowledge/documents/${id}/chunks`).subscribe({
      next:items=>this.chunks.set(items),error:()=>this.message.set('No se pudieron cargar los chunks.')
    });
  }
  upload(key:string,file:File,options:any){
    const form=new FormData(); form.append('file',file);
    Object.entries(options).forEach(([k,v])=>{if(v!==undefined&&v!==null&&v!=='')form.append(k,String(v));});
    this.loading.set(true);this.message.set('Ingestando y clasificando documento…');
    this.http.post<any>(`/api/knowledge/bases/${key}/files`,form).subscribe({
      next:r=>{this.loading.set(false);this.message.set(`Documento ingerido: ${r.ingestion?.chunks ?? 0} chunks, estado ${r.ingestion?.status ?? r.document?.status}.`);this.loadDocuments(key);},
      error:e=>{this.loading.set(false);this.message.set(e?.error?.detail||e?.error?.message||'Error durante la ingesta del documento.');}
    });
  }
  retrieve(text:string,mode:string,topK:number,baseKey:string){
    const payload={text,mode,top_k:topK,candidate_k:Math.max(topK*4,20),filters:{knowledge_base_keys:baseKey?[baseKey]:[]},expand_parents:true,ontology_enabled:true,vector_min_score:0.20,keyword_min_score:0.0,graph_min_score:0.0};
    this.loading.set(true);
    this.http.post<RetrievalResult>('/api/knowledge/retrieve',payload).subscribe({
      next:r=>{this.results.set(r);this.loading.set(false);},
      error:e=>{this.loading.set(false);this.message.set(e?.error?.detail||'No se pudo consultar el RAG.');}
    });
  }
}
