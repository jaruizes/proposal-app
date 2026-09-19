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
export interface OfferExecution{id:string;name:string;customer?:string;presentationLanguage:string;inputDriveFolder:string;outputDriveFolder:string;presentationName:string;presentationTemplateId?:string;provider:string;models:Record<string,string>;proposalGuidance?:{sections:ProposalSectionConfig[]};sections:any;currentStep:string;overallStatus:'Trabajando'|'Esperando aprobación'|'Cancelado'|'Completado'|'Error'|'Pendiente';createdAt:Date|string;phases:Phase[];}
