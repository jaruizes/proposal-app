import { CommonModule } from '@angular/common';
import { Component, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MockExecutionService } from './mock.service';
import { OfferExecution, Phase, SectionConfig } from './models';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './app.component.html'
})
export class AppComponent {
  svc = inject(MockExecutionService);
  view = signal<'home' | 'detail'>('home');
  selectedId = signal<string | null>(null);
  selectedPhaseKey = signal<string | null>(null);
  createOpen = signal(false);
  configOpen = signal(false);
  chatMessage = '';

  providerModels: Record<string, string[]> = {
    'AWS Bedrock': ['Claude Sonnet 4', 'Claude 3.7 Sonnet', 'Amazon Nova Pro'],
    'OpenAI': ['GPT-5', 'GPT-4.1'],
    'Anthropic': ['Claude Sonnet 4', 'Claude Opus 4'],
    'Google': ['Gemini 2.5 Pro', 'Gemini 2.5 Flash'],
    'xAI': ['Grok 4', 'Grok 3']
  };

  draft: any = this.newDraft();
  selected = computed(() => this.selectedId() ? this.svc.get(this.selectedId()!) : undefined);
  selectedPhase = computed(() => this.selected()?.phases.find(p => p.key === this.selectedPhaseKey()));

  stats = computed(() => {
    const items = this.svc.executions();
    return {
      total: items.length,
      working: items.filter(x => x.overallStatus === 'Trabajando').length,
      waiting: items.filter(x => x.overallStatus === 'Esperando aprobación').length
    };
  });

  openCreate() { this.draft = this.newDraft(); this.createOpen.set(true); }
  closeCreate() { this.createOpen.set(false); }
  saveCreate() { this.svc.create(this.draft); this.createOpen.set(false); }
  openDetail(exec: OfferExecution) {
    this.selectedId.set(exec.id); this.view.set('detail');
    const candidate = exec.phases.find(p => p.status === 'waiting_approval') || exec.phases.find(p => p.status === 'approved');
    this.selectedPhaseKey.set(candidate?.key || null);
  }
  back() { this.view.set('home'); this.selectedId.set(null); this.selectedPhaseKey.set(null); }
  phaseClickable(p: Phase) { return p.status === 'approved' || p.status === 'waiting_approval'; }
  choosePhase(p: Phase) { if (this.phaseClickable(p)) this.selectedPhaseKey.set(p.key); }
  approve() {
    const e = this.selected(); const p = this.selectedPhase();
    if (e && p) { this.svc.approve(e.id, p.key); this.selectedPhaseKey.set(null); }
  }
  sendRefine() {
    const e = this.selected(); const p = this.selectedPhase();
    if (e && p && this.chatMessage.trim()) {
      this.svc.refine(e.id, p.key, this.chatMessage.trim());
      this.chatMessage = '';
    }
  }
  statusClass(status: string) { return status === 'Trabajando' ? 'working' : status === 'Esperando aprobación' ? 'waiting' : 'cancelled'; }
  phaseClass(status: string) { return status.replace('_', '-'); }
  currentModels() { return this.providerModels[this.draft.provider] || []; }
  addSection() { this.draft.sections.push({ name: 'Nueva sección', maxSlides: 3, enabled: true }); }
  removeSection(i: number) { this.draft.sections.splice(i, 1); }

  private newDraft() {
    return {
      name: '', presentationLanguage: 'Español', inputDriveFolder: '/Propuestas/Entrada', outputDriveFolder: '/Propuestas/Salida',
      presentationName: '', provider: 'AWS Bedrock', models: {
        analysis: 'Claude Sonnet 4', strategy: 'Claude Sonnet 4', solution: 'Claude Sonnet 4', slides: 'Claude Sonnet 4'
      },
      sections: structuredClone(this.svc.defaultSections) as SectionConfig[]
    };
  }
}
