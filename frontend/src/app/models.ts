export type PhaseStatus='pending'|'working'|'waiting_approval'|'approved'|'cancelled'|'failed'|'stale';
export interface Phase{key:string;label:string;status:PhaseStatus;output?:string;errorMessage?:string;}
export interface SectionConfig{name:string;maxSlides:number;enabled:boolean;}
export interface ProposalSectionConfig{name:string;enabled:boolean;depth:'SUMMARY'|'STANDARD'|'DETAILED';guidance:string;}
export interface AgentExecutionTelemetry{
  id:string;offerId:string;phase:string;agentKey:string;
  status:'PENDING'|'RUNNING'|'COMPLETED'|'FAILED'|'CANCELLED'|string;
  objective?:string;output?:string;model?:string;inputTokens:number;outputTokens:number;
  providerRequestId?:string;startedAt?:Date|string;completedAt?:Date|string;errorMessage?:string;checkpointKey?:string;inputFingerprint?:string;reusedFromExecutionId?:string;
  telemetry?:{
    proposal_step_usage?:Array<{stage:string;section?:string;reused?:boolean;input_tokens:number;output_tokens:number;cache_read_tokens:number;cache_write_tokens:number;estimated_cost_usd:number;cumulative_cost_usd:number}>;
    proposal_consumed?:{input_tokens:number;output_tokens:number;cache_read_tokens:number;cache_write_tokens:number;estimated_cost_usd:number};
    proposal_budget?:{input_tokens:number;output_tokens:number;cost_usd:number};
  };
}
export interface OfferExecution{id:string;name:string;customer?:string;presentationLanguage:string;inputDriveFolder:string;outputDriveFolder:string;presentationName:string;generatePresentation:boolean;provider:string;models:Record<string,string>;proposalGuidance?:{sections:ProposalSectionConfig[]};sections:any;currentStep:string;overallStatus:'Trabajando'|'Esperando aprobación'|'Cancelado'|'Completado'|'Error'|'Pendiente';createdAt:Date|string;phases:Phase[];}

export interface MaterializedDocument {
  id:string;type:'PROPOSAL_DOCX'|'PROPOSAL_PDF'|string;contentVersion:number;renderVersion:number;
  mediaType:string;fileName:string;templateId:string;rendererVersion:string;sourceHash:string;
  status:'PROCESSING'|'READY'|'FAILED';errorMessage?:string;createdAt:string;updatedAt:string;
}
export interface TemplateSettings {proposalTemplateId:string;presentationTemplateId:string;updatedAt?:string;}
