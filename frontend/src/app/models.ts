export type PhaseStatus='pending'|'working'|'waiting_approval'|'approved'|'cancelled'|'failed'|'stale';
export interface Phase{key:string;label:string;status:PhaseStatus;output?:string;errorMessage?:string;}
export interface SectionConfig{name:string;maxSlides:number;enabled:boolean;}
export interface ProposalSectionConfig{name:string;enabled:boolean;depth:'SUMMARY'|'STANDARD'|'DETAILED';guidance:string;}
export interface AgentExecutionTelemetry{
  id:string;offerId:string;phase:string;agentKey:string;
  status:'PENDING'|'RUNNING'|'COMPLETED'|'FAILED'|'CANCELLED'|string;
  objective?:string;output?:string;model?:string;inputTokens:number;outputTokens:number;
  providerRequestId?:string;startedAt?:Date|string;completedAt?:Date|string;errorMessage?:string;
}
export interface OfferExecution{id:string;name:string;customer?:string;presentationLanguage:string;inputDriveFolder:string;outputDriveFolder:string;presentationName:string;generatePresentation:boolean;provider:string;models:Record<string,string>;proposalGuidance?:{sections:ProposalSectionConfig[]};sections:any;currentStep:string;overallStatus:'Trabajando'|'Esperando aprobación'|'Cancelado'|'Completado'|'Error'|'Pendiente';createdAt:Date|string;phases:Phase[];}

export interface MaterializedDocument {
  id:string;type:'PROPOSAL_DOCX'|'PROPOSAL_PDF'|string;contentVersion:number;renderVersion:number;
  mediaType:string;fileName:string;templateId:string;rendererVersion:string;sourceHash:string;
  status:'PROCESSING'|'READY'|'FAILED';errorMessage?:string;createdAt:string;updatedAt:string;
}
export interface TemplateSettings {proposalTemplateId:string;presentationTemplateId:string;updatedAt?:string;}
