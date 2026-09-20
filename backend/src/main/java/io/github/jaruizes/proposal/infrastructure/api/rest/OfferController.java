package io.github.jaruizes.proposal.infrastructure.api.rest;
import io.github.jaruizes.proposal.business.ArtifactExportService; import io.github.jaruizes.proposal.business.OfferWorkflowService; import io.github.jaruizes.proposal.business.ProposalDocumentMaterializationService; import io.github.jaruizes.proposal.domain.model.ArtifactType; import io.github.jaruizes.proposal.domain.model.PhaseType; import io.github.jaruizes.proposal.infrastructure.api.rest.dto.*; import io.github.jaruizes.proposal.infrastructure.api.rest.mapper.OfferRestMapper; import jakarta.validation.Valid; import org.springframework.http.ContentDisposition; import org.springframework.http.HttpHeaders; import org.springframework.http.MediaType; import org.springframework.http.ResponseEntity; import org.springframework.web.bind.annotation.*; import org.springframework.web.servlet.mvc.method.annotation.SseEmitter; import java.io.IOException; import java.util.*; import java.util.concurrent.*;
@RestController @RequestMapping("/api/offers") @CrossOrigin(origins="*") public class OfferController {private final OfferWorkflowService workflow;private final ArtifactExportService artifactExports;private final ProposalDocumentMaterializationService proposalDocuments;private final ScheduledExecutorService scheduler=Executors.newScheduledThreadPool(1);public OfferController(OfferWorkflowService w,ArtifactExportService artifactExports,ProposalDocumentMaterializationService proposalDocuments){workflow=w;this.artifactExports=artifactExports;this.proposalDocuments=proposalDocuments;}
@GetMapping public List<OfferResponse> all(){return workflow.findAll().stream().map(o->OfferRestMapper.toResponse(o,workflow.phases(o.id()),workflow.artifacts(o.id()))).toList();}
@GetMapping("/{id}") public OfferResponse one(@PathVariable UUID id){var o=workflow.find(id);return OfferRestMapper.toResponse(o,workflow.phases(id),workflow.artifacts(id));}
@PostMapping public OfferResponse create(@Valid @RequestBody CreateOfferRequest r){var offer=workflow.create(new OfferWorkflowService.CreateOfferCommand(r.name(),blank(r.customer(),r.name()),blank(r.language(),"es"),blank(r.presentationLanguage(),"es"),blank(r.inputDriveFolder(),""),blank(r.outputDriveFolder(),""),r.presentationName(),blank(r.presentationTemplateId(),""),blank(r.proposalTemplateId(),""),blank(r.aiProvider(),"ANTHROPIC"),r.models()==null?Map.of():r.models(),r.proposalGuidance(),r.presentationGuidance()));return OfferRestMapper.toResponse(offer,workflow.phases(offer.id()),workflow.artifacts(offer.id()));}
@PostMapping("/{id}/phases/{phase}/approve") public void approve(@PathVariable UUID id,@PathVariable String phase){workflow.approve(id,parse(phase));}
@PostMapping("/{id}/phases/{phase}/refine") public void refine(@PathVariable UUID id,@PathVariable String phase,@Valid @RequestBody RefinePhaseRequest r){workflow.refine(id,parse(phase),r.instruction());}
@PostMapping("/{id}/phases/{phase}/retry") public void retry(@PathVariable UUID id,@PathVariable String phase){workflow.retry(id,parse(phase));}
@PutMapping("/{id}/configuration") public OfferResponse updateConfiguration(@PathVariable UUID id,@RequestBody UpdateOfferConfigurationRequest r){var offer=workflow.updateConfiguration(id,new OfferWorkflowService.UpdateOfferConfigurationCommand(r.presentationLanguage(),r.inputDriveFolder(),r.outputDriveFolder(),r.presentationName(),r.presentationTemplateId(),r.proposalTemplateId(),r.aiProvider(),r.models(),r.proposalGuidance(),r.presentationGuidance()));return OfferRestMapper.toResponse(offer,workflow.phases(id),workflow.artifacts(id));}
@GetMapping("/{id}/agents") public Object agents(@PathVariable UUID id){return workflow.agentExecutions(id);}
@GetMapping("/{id}/artifacts/{type}/{version}/pdf") public ResponseEntity<byte[]> exportArtifactPdf(@PathVariable UUID id,@PathVariable String type,@PathVariable int version){
    var rendered=artifactExports.exportPdf(id,ArtifactType.valueOf(type.toUpperCase(Locale.ROOT)),version);
    var headers=new HttpHeaders();
    headers.setContentType(MediaType.APPLICATION_PDF);
    headers.setContentDisposition(ContentDisposition.attachment().filename(rendered.fileName()).build());
    headers.set("X-Renderer-Version",rendered.rendererVersion());
    headers.set("X-Template-Id",rendered.templateId());
    return ResponseEntity.ok().headers(headers).body(rendered.content());
}
@GetMapping("/{id}/documents") public Object documents(@PathVariable UUID id){
    return proposalDocuments.list(id).stream().map(d->Map.of(
            "id",d.id().toString(),"type",d.type().name(),"contentVersion",d.contentVersion(),"renderVersion",d.renderVersion(),
            "mediaType",d.mediaType(),"fileName",d.fileName(),"templateId",d.templateId(),"rendererVersion",d.rendererVersion(),
            "sourceHash",d.sourceHash(),"status",d.status().name(),"errorMessage",Objects.toString(d.errorMessage(),""),
            "createdAt",d.createdAt().toString(),"updatedAt",d.updatedAt().toString())).toList();
}
@PostMapping("/{id}/documents/materialize") public Object materializeDocuments(@PathVariable UUID id){return proposalDocuments.materializeApprovedProposal(id).stream().map(d->Map.of("id",d.id(),"type",d.type(),"status",d.status(),"renderVersion",d.renderVersion())).toList();}
@GetMapping("/{id}/documents/{documentId}/download") public ResponseEntity<byte[]> downloadDocument(@PathVariable UUID id,@PathVariable UUID documentId){
    var d=proposalDocuments.find(id,documentId);
    if(d.status()!=io.github.jaruizes.proposal.domain.model.DocumentMaterializationStatus.READY||d.content()==null)throw new IllegalArgumentException("Document is not ready");
    var headers=new HttpHeaders();headers.setContentType(MediaType.parseMediaType(d.mediaType()));headers.setContentDisposition(ContentDisposition.attachment().filename(d.fileName()).build());
    headers.set("X-Content-Version",Integer.toString(d.contentVersion()));headers.set("X-Render-Version",Integer.toString(d.renderVersion()));headers.set("X-Renderer-Version",d.rendererVersion());
    return ResponseEntity.ok().headers(headers).body(d.content());
}
@GetMapping(path="/{id}/events",produces=MediaType.TEXT_EVENT_STREAM_VALUE) public SseEmitter events(@PathVariable UUID id){var emitter=new SseEmitter(0L);var f=scheduler.scheduleAtFixedRate(()->{try{emitter.send(SseEmitter.event().name("offer").data(one(id)));}catch(IOException|RuntimeException ex){emitter.complete();}},0,2,TimeUnit.SECONDS);emitter.onCompletion(()->f.cancel(true));emitter.onTimeout(()->f.cancel(true));return emitter;}
public record UpdateOfferConfigurationRequest(String presentationLanguage,String inputDriveFolder,String outputDriveFolder,String presentationName,String presentationTemplateId,String proposalTemplateId,String aiProvider,Map<String,String> models,Object proposalGuidance,Object presentationGuidance) {}
private static String blank(String v,String d){return v==null||v.isBlank()?d:v;} private static PhaseType parse(String p){return switch(p){case"analysis"->PhaseType.ANALYSIS;case"strategy"->PhaseType.STRATEGY;case"solution"->PhaseType.SOLUTION;case"proposal"->PhaseType.PROPOSAL;case"slide-plan"->PhaseType.SLIDE_PLAN;case"presentation"->PhaseType.PRESENTATION;default->throw new IllegalArgumentException("Unknown phase");};}}
