import { Injectable, signal } from '@angular/core';
import { OfferExecution, Phase, SectionConfig } from './models';

@Injectable({ providedIn: 'root' })
export class MockExecutionService {
  readonly phasesTemplate: Phase[] = [
    { key: 'analysis', label: 'Entendimiento y cualificación', status: 'pending' },
    { key: 'strategy', label: 'Estrategia de respuesta', status: 'pending' },
    { key: 'solution', label: 'Definición de solución', status: 'pending' },
    { key: 'slide-plan', label: 'Plan de slides', status: 'pending' },
    { key: 'presentation', label: 'Presentación corporativa', status: 'pending' }
  ];

  readonly defaultSections: SectionConfig[] = [
    { name: 'Resumen ejecutivo', maxSlides: 3, enabled: true },
    { name: 'Introducción, contexto y objetivos', maxSlides: 5, enabled: true },
    { name: 'Alcance y consideraciones', maxSlides: 5, enabled: true },
    { name: '¿Qué proponemos?', maxSlides: 10, enabled: true },
    { name: '¿Cómo lo vamos a hacer?', maxSlides: 10, enabled: true }
  ];

  executions = signal<OfferExecution[]>([
    this.seed('REDEIA · SSIR', 'Estrategia de respuesta', 'Esperando aprobación', 1),
    this.seed('Retail Data Platform 2027', 'Definición de solución', 'Trabajando', 2),
    this.seed('Modernización Portal Cliente', 'Presentación corporativa', 'Esperando aprobación', 4)
  ]);

  private seed(name: string, currentStep: string, overallStatus: OfferExecution['overallStatus'], currentIndex: number): OfferExecution {
    const phases = this.phasesTemplate.map((p, i) => ({
      ...p,
      status: i < currentIndex ? 'approved' : i === currentIndex ? (overallStatus === 'Trabajando' ? 'working' : 'waiting_approval') : 'pending',
      output: i <= currentIndex ? this.mockOutput(p.label, name) : undefined
    } as Phase));
    return {
      id: crypto.randomUUID(), name, presentationLanguage: 'Español', inputDriveFolder: '/Propuestas/Entrada',
      outputDriveFolder: '/Propuestas/Salida', presentationName: `${name} - Propuesta`, provider: 'AWS Bedrock',
      models: { analysis: 'Claude Sonnet 4', strategy: 'Claude Sonnet 4', solution: 'Claude Sonnet 4', slides: 'Claude Sonnet 4' },
      sections: structuredClone(this.defaultSections), currentStep, overallStatus, createdAt: new Date(), phases
    };
  }

  create(data: Partial<OfferExecution>): OfferExecution {
    const phases = this.phasesTemplate.map((p, i) => ({ ...p, status: i === 0 ? 'working' : 'pending' } as Phase));
    const offer: OfferExecution = {
      id: crypto.randomUUID(),
      name: data.name || 'Nueva oferta',
      presentationLanguage: data.presentationLanguage || 'Español',
      inputDriveFolder: data.inputDriveFolder || '',
      outputDriveFolder: data.outputDriveFolder || '',
      presentationName: data.presentationName || '',
      provider: data.provider || 'AWS Bedrock',
      models: data.models || {},
      sections: data.sections || structuredClone(this.defaultSections),
      currentStep: phases[0].label,
      overallStatus: 'Trabajando',
      createdAt: new Date(),
      phases
    };
    this.executions.update(items => [offer, ...items]);
    setTimeout(() => this.finishWorkingPhase(offer.id), 3500);
    return offer;
  }

  get(id: string) { return this.executions().find(e => e.id === id); }

  approve(id: string, phaseKey: string) {
    this.executions.update(items => items.map(exec => {
      if (exec.id !== id) return exec;
      const phases = exec.phases.map(p => p.key === phaseKey ? { ...p, status: 'approved' as const } : p);
      const idx = phases.findIndex(p => p.key === phaseKey);
      if (idx < phases.length - 1) phases[idx + 1] = { ...phases[idx + 1], status: 'working' };
      const next = phases[idx + 1];
      return { ...exec, phases, currentStep: next?.label ?? 'Completado', overallStatus: next ? 'Trabajando' : 'Esperando aprobación' };
    }));
    setTimeout(() => this.finishWorkingPhase(id), 3500);
  }

  refine(id: string, phaseKey: string, message: string) {
    this.executions.update(items => items.map(exec => exec.id === id ? {
      ...exec,
      overallStatus: 'Trabajando',
      currentStep: exec.phases.find(p => p.key === phaseKey)?.label || exec.currentStep,
      phases: exec.phases.map(p => p.key === phaseKey ? { ...p, status: 'working' as const, output: `${p.output || ''}\n\n> Solicitud de cambio: ${message}` } : p)
    } : exec));
    setTimeout(() => this.finishWorkingPhase(id, phaseKey), 2800);
  }

  private finishWorkingPhase(id: string, explicitKey?: string) {
    this.executions.update(items => items.map(exec => {
      if (exec.id !== id) return exec;
      const key = explicitKey || exec.phases.find(p => p.status === 'working')?.key;
      if (!key) return exec;
      const phases = exec.phases.map(p => p.key === key ? { ...p, status: 'waiting_approval' as const, output: this.mockOutput(p.label, exec.name) } : p);
      const phase = phases.find(p => p.key === key)!;
      return { ...exec, phases, currentStep: phase.label, overallStatus: 'Esperando aprobación' };
    }));
  }

  private mockOutput(step: string, name: string) {
    return `# ${step}\n\n## ${name}\n\nEste es un **artefacto simulado** para validar el flujo visual.\n\n- Alcance principal identificado y estructurado.\n- Decisiones relevantes trazadas.\n- Riesgos y dependencias visibles para revisión humana.\n\n### Siguiente decisión\n\nRevisar este contenido y **validar** o solicitar cambios desde el panel de refinamiento.`;
  }
}
