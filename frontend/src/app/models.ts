export type PhaseStatus='pending'|'working'|'waiting_approval'|'approved'|'cancelled';
export interface Phase{key:string;label:string;status:PhaseStatus;output?:string;}
export interface SectionConfig{name:string;maxSlides:number;enabled:boolean;}
export interface OfferExecution{id:string;name:string;customer?:string;presentationLanguage:string;inputDriveFolder:string;outputDriveFolder:string;presentationName:string;provider:string;models:Record<string,string>;sections:any;currentStep:string;overallStatus:'Trabajando'|'Esperando aprobación'|'Cancelado'|'Completado'|'Error'|'Pendiente';createdAt:Date|string;phases:Phase[];}
