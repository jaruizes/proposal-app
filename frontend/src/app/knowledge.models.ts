export interface KnowledgeBase {
  id:string; key:string; name:string; description:string; enabled:boolean;
  metadata:Record<string,unknown>; created_at:string;
}
export interface KnowledgeDocument {
  id:string; knowledge_base_key:string; title:string; media_type:string; source_uri?:string;
  metadata:Record<string,any>; status:'STORED'|'PROCESSING'|'READY'|'FAILED'|'ARCHIVED'|'SUPERSEDED'; family_id:string; version:number; previous_version_id?:string; created_at:string;
}
export interface KnowledgeChunk {
  id:string; document_id:string; ordinal:number; content:string; metadata:Record<string,any>;
  embedding_model?:string;
}
export interface RetrievalHit {
  chunk_id:string; document_id:string; knowledge_base_key:string; title:string; content:string;
  score:number; retrieval_method:string; metadata:Record<string,any>; source_uri?:string;
}
export interface RetrievalResult {
  query:string; mode:string; hits:RetrievalHit[]; embedding_model?:string; metadata:Record<string,any>;
}
