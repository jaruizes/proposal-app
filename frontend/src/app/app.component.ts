import { CommonModule } from '@angular/common';
import { Component, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ExecutionService } from './execution.service';
import { OfferExecution, Phase, SectionConfig } from './models';
@Component({selector:'app-root',standalone:true,imports:[CommonModule,FormsModule],templateUrl:'./app.component.html'})
export class AppComponent {
  svc=inject(ExecutionService); view=signal<'home'|'detail'>('home'); selectedId=signal<string|null>(null); selectedPhaseKey=signal<string|null>(null); createOpen=signal(false); configOpen=signal(false); showRawMarkdown=signal(false); chatMessage='';
  providerModels:Record<string,string[]>={ANTHROPIC:['claude-sonnet-4-6','claude-opus-4-6'],'AWS Bedrock':['claude-sonnet-4-6'],OpenAI:['gpt-5.6']};
  draft:any=this.newDraft(); selected=computed(()=>this.selectedId()?this.svc.get(this.selectedId()!):undefined); selectedPhase=computed(()=>this.selected()?.phases.find(p=>p.key===this.selectedPhaseKey()));
  stats=computed(()=>{const items=this.svc.executions();return{total:items.length,working:items.filter(x=>x.overallStatus==='Trabajando').length,waiting:items.filter(x=>x.overallStatus==='Esperando aprobación').length};});
  openCreate(){this.draft=this.newDraft();this.createOpen.set(true);} closeCreate(){this.createOpen.set(false);} saveCreate(){this.svc.create(this.draft);this.createOpen.set(false);}
  openDetail(exec:OfferExecution){this.selectedId.set(exec.id);this.view.set('detail');this.svc.watch(exec.id);const candidate=exec.phases.find(p=>p.status==='waiting_approval')||exec.phases.find(p=>p.status==='approved');this.selectedPhaseKey.set(candidate?.key||null);this.showRawMarkdown.set(false);}
  back(){this.view.set('home');this.selectedId.set(null);this.selectedPhaseKey.set(null);this.showRawMarkdown.set(false);} phaseClickable(p:Phase){return p.status==='approved'||p.status==='waiting_approval';} choosePhase(p:Phase){if(this.phaseClickable(p)){this.selectedPhaseKey.set(p.key);this.showRawMarkdown.set(false);}}
  approve(){const e=this.selected(),p=this.selectedPhase();if(e&&p){this.svc.approve(e.id,p.key);this.selectedPhaseKey.set(null);}}
  sendRefine(){const e=this.selected(),p=this.selectedPhase();if(e&&p&&this.chatMessage.trim()){this.svc.refine(e.id,p.key,this.chatMessage.trim());this.chatMessage='';}}
  statusClass(status:string){return status==='Trabajando'?'working':status==='Esperando aprobación'?'waiting':status==='Completado'?'approved':'cancelled';} phaseClass(status:string){return status.replace('_','-');} currentModels(){return this.providerModels[this.draft.provider]||[];} addSection(){this.draft.sections.push({name:'Nueva sección',maxSlides:3,enabled:true});} removeSection(i:number){this.draft.sections.splice(i,1);}

  renderMarkdown(markdown:string|undefined):string {
    if (!markdown) return '<p>El artefacto todavía no está disponible.</p>';
    const lines=markdown.replace(/\r\n/g,'\n').split('\n');
    const html:string[]=[];
    let inCode=false; let code:string[]=[]; let listType:''|'ul'|'ol'='';
    const closeList=()=>{if(listType){html.push(`</${listType}>`);listType='';}};
    for(let i=0;i<lines.length;i++){
      const line=lines[i];
      if(line.trim().startsWith('```')){closeList();if(inCode){html.push(`<pre><code>${this.escapeHtml(code.join('\n'))}</code></pre>`);code=[];}inCode=!inCode;continue;}
      if(inCode){code.push(line);continue;}
      if(this.isTableHeader(lines,i)){
        closeList(); const headers=this.tableCells(line); i+=2; const rows:string[][]=[];
        while(i<lines.length&&this.isTableRow(lines[i])){rows.push(this.tableCells(lines[i]));i++;}
        i--;
        html.push('<div style="overflow-x:auto"><table style="width:100%;border-collapse:collapse;margin:1rem 0"><thead><tr>'+headers.map(h=>`<th style="text-align:left;border:1px solid #29324a;padding:.6rem">${this.inlineMarkdown(h)}</th>`).join('')+'</tr></thead><tbody>'+rows.map(r=>'<tr>'+r.map(c=>`<td style="vertical-align:top;border:1px solid #29324a;padding:.6rem">${this.inlineMarkdown(c)}</td>`).join('')+'</tr>').join('')+'</tbody></table></div>');
        continue;
      }
      const heading=line.match(/^(#{1,6})\s+(.+)$/); if(heading){closeList();const level=heading[1].length;html.push(`<h${level} style="margin:1.4rem 0 .7rem">${this.inlineMarkdown(heading[2])}</h${level}>`);continue;}
      const bullet=line.match(/^\s*[-*+]\s+(.+)$/); if(bullet){if(listType!=='ul'){closeList();listType='ul';html.push('<ul>');}html.push(`<li>${this.inlineMarkdown(bullet[1])}</li>`);continue;}
      const ordered=line.match(/^\s*\d+[.)]\s+(.+)$/); if(ordered){if(listType!=='ol'){closeList();listType='ol';html.push('<ol>');}html.push(`<li>${this.inlineMarkdown(ordered[1])}</li>`);continue;}
      closeList(); if(!line.trim()){html.push('<div style="height:.45rem"></div>');continue;}
      html.push(`<p style="margin:.45rem 0;line-height:1.65">${this.inlineMarkdown(line)}</p>`);
    }
    closeList(); if(inCode)html.push(`<pre><code>${this.escapeHtml(code.join('\n'))}</code></pre>`);
    return html.join('');
  }
  private isTableHeader(lines:string[],i:number){return i+1<lines.length&&this.isTableRow(lines[i])&&/^\s*\|?\s*:?-{3,}/.test(lines[i+1])&&lines[i+1].includes('|');}
  private isTableRow(line:string){return line.includes('|')&&line.trim().length>0;}
  private tableCells(line:string){return line.trim().replace(/^\|/,'').replace(/\|$/,'').split('|').map(x=>x.trim());}
  private inlineMarkdown(value:string){let s=this.escapeHtml(value);s=s.replace(/`([^`]+)`/g,'<code>$1</code>').replace(/\*\*([^*]+)\*\*/g,'<strong>$1</strong>').replace(/__([^_]+)__/g,'<strong>$1</strong>').replace(/\*([^*]+)\*/g,'<em>$1</em>');return s;}
  private escapeHtml(value:string){return value.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#039;');}
  private newDraft(){return{name:'',customer:'',presentationLanguage:'Español',inputDriveFolder:'',outputDriveFolder:'',presentationName:'',provider:'ANTHROPIC',models:{analysis:'claude-sonnet-4-6',strategy:'claude-sonnet-4-6',solution:'claude-sonnet-4-6',slides:'claude-sonnet-4-6'},sections:structuredClone(this.svc.defaultSections) as SectionConfig[]};}
}
