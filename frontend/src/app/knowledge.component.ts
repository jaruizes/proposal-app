import { CommonModule } from '@angular/common';
import { Component, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { KnowledgeService } from './knowledge.service';
import { KnowledgeDocument } from './knowledge.models';

@Component({selector:'app-knowledge',standalone:true,imports:[CommonModule,FormsModule],templateUrl:'./knowledge.component.html'})
export class KnowledgeComponent implements OnInit {
  svc=inject(KnowledgeService);
  selectedBase=signal('');
  uploadOpen=signal(false);
  selectedDocument=signal<KnowledgeDocument|null>(null);
  query=''; queryMode='hybrid'; topK=5; file:File|null=null;
  upload:any={chunkingStrategy:'fixed',metadataEnrichment:'standard',chunkSize:1200,overlap:200,parentSize:6000,childSize:1200,childOverlap:200,maxKeywords:8,customer:'',sector:'',year:new Date().getFullYear(),proposalType:'',tags:''};

  ngOnInit(){this.svc.loadBases();}
  chooseBase(key:string){this.selectedBase.set(key);this.selectedDocument.set(null);this.svc.chunks.set([]);this.svc.loadDocuments(key);}
  onFile(event:Event){const input=event.target as HTMLInputElement;this.file=input.files?.[0]||null;}
  doUpload(){if(this.file&&this.selectedBase()){this.svc.upload(this.selectedBase(),this.file,this.upload);this.uploadOpen.set(false);this.file=null;}}
  search(){if(this.query.trim())this.svc.retrieve(this.query.trim(),this.queryMode,this.topK,this.selectedBase());}
  inspect(doc:KnowledgeDocument){this.selectedDocument.set(doc);this.svc.loadChunks(doc.id);}
  classification(doc:KnowledgeDocument){return doc.metadata?.['classification']?.['document_type']||'GENERAL_REFERENCE';}
  keywords(doc:KnowledgeDocument){return (doc.metadata?.['enrichment']?.['keywords']||[]).slice(0,6);}
}
