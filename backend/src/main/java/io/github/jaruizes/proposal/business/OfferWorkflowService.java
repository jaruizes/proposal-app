package io.github.jaruizes.proposal.business;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import io.github.jaruizes.proposal.domain.exceptions.DomainException;
import io.github.jaruizes.proposal.domain.model.*;
import io.github.jaruizes.proposal.domain.ports.*;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.core.task.TaskExecutor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.transaction.support.TransactionSynchronization;
import org.springframework.transaction.support.TransactionSynchronizationManager;

import java.time.Instant;
import java.util.*;

@Service
public class OfferWorkflowService {
    private final OfferRepositoryPort offers;
    private final PhaseRepositoryPort phases;
    private final ArtifactRepositoryPort artifacts;
    private final AgentExecutionRepositoryPort agentExecutions;
    private final AgentRuntimeService agents;
    private final AgentRegistryService agentRegistry;
    private final SourceIngestionService sources;
    private final PresentationPort presentations;
    private final SlidePlanValidator slidePlanValidator;
    private final TaskExecutor phaseTaskExecutor;
    private final TaskExecutor documentTaskExecutor;
    private final ProposalDocumentMaterializationService proposalDocuments;
    private final ObjectMapper json = new ObjectMapper();

    public OfferWorkflowService(OfferRepositoryPort offers, PhaseRepositoryPort phases,
                                ArtifactRepositoryPort artifacts, AgentExecutionRepositoryPort agentExecutions,
                                AgentRuntimeService agents, AgentRegistryService agentRegistry,
                                SourceIngestionService sources, PresentationPort presentations,
                                SlidePlanValidator slidePlanValidator,
                                ProposalDocumentMaterializationService proposalDocuments,
                                @Qualifier("agentTaskExecutor") TaskExecutor phaseTaskExecutor,
                                @Qualifier("documentTaskExecutor") TaskExecutor documentTaskExecutor) {
        this.offers=offers; this.phases=phases; this.artifacts=artifacts; this.agentExecutions=agentExecutions;
        this.agents=agents; this.agentRegistry=agentRegistry; this.sources=sources; this.presentations=presentations;
        this.slidePlanValidator=slidePlanValidator; this.phaseTaskExecutor=phaseTaskExecutor; this.documentTaskExecutor=documentTaskExecutor;
        this.proposalDocuments=proposalDocuments;
    }

    @Transactional
    public Offer create(CreateOfferCommand command) {
        var proposalGuidance=normalizeProposalGuidance(command.proposalGuidance());
        validateConfiguration(command.presentationLanguage(),command.inputDriveFolder(),command.outputDriveFolder(),command.presentationName(),command.generatePresentation(),command.aiProvider(),command.models(),proposalGuidance,command.presentationGuidance());
        var now=Instant.now();
        var offer=new Offer(UUID.randomUUID(),command.name(),command.customer(),command.language(),command.presentationLanguage(),
                command.inputDriveFolder(),command.outputDriveFolder(),command.presentationName(),"","",command.generatePresentation(),command.aiProvider(),
                command.models(),proposalGuidance,command.presentationGuidance(),PhaseType.ANALYSIS,ExecutionStatus.RUNNING,now,now);
        offer=offers.save(offer);
        for(var phase:PhaseType.values()) phases.save(new PhaseExecution(UUID.randomUUID(),offer.id(),phase,
                phase==PhaseType.ANALYSIS?ExecutionStatus.RUNNING:(!command.generatePresentation()&&(phase==PhaseType.SLIDE_PLAN||phase==PhaseType.PRESENTATION)?ExecutionStatus.CANCELLED:ExecutionStatus.NOT_STARTED),1,null,
                phase==PhaseType.ANALYSIS?now:null,null));
        submitPhase(offer.id(),PhaseType.ANALYSIS,null);
        return offer;
    }

    public List<Offer> findAll(){return offers.findAll();}
    public Offer find(UUID id){return offers.findById(id).orElseThrow(()->new DomainException("Offer not found"));}
    public List<PhaseExecution> phases(UUID id){return phases.findByOfferId(id);}
    public List<Artifact> artifacts(UUID id){return artifacts.findByOfferId(id);}
    public List<AgentExecution> agentExecutions(UUID id){return agentExecutions.findByOfferId(id);}

    @Transactional
    public void approve(UUID offerId,PhaseType phaseType){
        var phase=phases.find(offerId,phaseType).orElseThrow(()->new DomainException("Phase not found"));
        if(phase.status()!=ExecutionStatus.WAITING_FOR_HUMAN) throw new DomainException("Phase is not waiting for approval");
        phases.save(new PhaseExecution(phase.id(),offerId,phaseType,ExecutionStatus.APPROVED,phase.version(),null,phase.startedAt(),Instant.now()));
        if(phaseType==PhaseType.PROPOSAL) submitProposalMaterialization(offerId);
        var offer=find(offerId);
        if(phaseType==PhaseType.PROPOSAL&&!offer.generatePresentation()){
            offers.save(copyOffer(offer,PhaseType.PROPOSAL,ExecutionStatus.APPROVED));
            return;
        }
        var next=phaseType.next();
        if(next==null){offers.save(copyOffer(offer,phaseType,ExecutionStatus.APPROVED));return;}
        var n=phases.find(offerId,next).orElseThrow();
        phases.save(new PhaseExecution(n.id(),offerId,next,ExecutionStatus.RUNNING,n.version(),null,Instant.now(),null));
        offers.save(copyOffer(offer,next,ExecutionStatus.RUNNING));
        submitPhase(offerId,next,null);
    }

    @Transactional
    public Offer updateConfiguration(UUID offerId,UpdateOfferConfigurationCommand command){
        var current=find(offerId);
        var presentationLanguage=blankOr(command.presentationLanguage(),current.presentationLanguage());
        var inputDriveFolder=blankOr(command.inputDriveFolder(),current.inputDriveFolder());
        var outputDriveFolder=blankOr(command.outputDriveFolder(),current.outputDriveFolder());
        var presentationName=blankOr(command.presentationName(),current.presentationName());
        var generatePresentation=command.generatePresentation()==null?current.generatePresentation():command.generatePresentation();
        var aiProvider=blankOr(command.aiProvider(),current.aiProvider());
        var models=command.models()==null||command.models().isEmpty()?current.models():command.models();
        var proposalGuidance=command.proposalGuidance()==null?current.proposalGuidance():normalizeProposalGuidance(command.proposalGuidance());
        var guidance=command.presentationGuidance()==null?current.presentationGuidance():command.presentationGuidance();
        validateConfiguration(presentationLanguage,inputDriveFolder,outputDriveFolder,presentationName,generatePresentation,aiProvider,models,proposalGuidance,guidance);
        var updated=new Offer(current.id(),current.name(),current.customer(),current.language(),presentationLanguage,inputDriveFolder,outputDriveFolder,presentationName,"","",generatePresentation,aiProvider,models,proposalGuidance,guidance,current.currentPhase(),current.status(),current.createdAt(),Instant.now());
        if(generatePresentation!=current.generatePresentation()) updateOptionalPresentationPhases(offerId,generatePresentation);

        return offers.save(updated);
    }

    @Transactional
    public void retry(UUID offerId,PhaseType phaseType){
        var phase=phases.find(offerId,phaseType).orElseThrow(()->new DomainException("Phase not found"));
        if(phase.status()!=ExecutionStatus.FAILED) throw new DomainException("Only failed phases can be retried");
        var offer=find(offerId);
        validateConfiguration(offer.presentationLanguage(),offer.inputDriveFolder(),offer.outputDriveFolder(),offer.presentationName(),offer.generatePresentation(),offer.aiProvider(),offer.models(),offer.proposalGuidance(),offer.presentationGuidance());
        phases.save(new PhaseExecution(phase.id(),offerId,phaseType,ExecutionStatus.RUNNING,phase.version()+1,null,Instant.now(),null));
        offers.save(copyOffer(offer,phaseType,ExecutionStatus.RUNNING));
        submitPhase(offerId,phaseType,null);
    }

    @Transactional
    public void refine(UUID offerId,PhaseType phaseType,String instruction){
        var phase=phases.find(offerId,phaseType).orElseThrow(()->new DomainException("Phase not found"));
        if(phase.status()==ExecutionStatus.RUNNING) throw new DomainException("Phase is already running");
        invalidateDownstream(offerId,phaseType);
        phases.save(new PhaseExecution(phase.id(),offerId,phaseType,ExecutionStatus.RUNNING,phase.version()+1,null,Instant.now(),null));
        offers.save(copyOffer(find(offerId),phaseType,ExecutionStatus.RUNNING));
        submitPhase(offerId,phaseType,instruction);
    }

    private void invalidateDownstream(UUID offerId,PhaseType from){
        var current=from.next();
        while(current!=null){
            var p=phases.find(offerId,current).orElseThrow();
            phases.save(new PhaseExecution(p.id(),offerId,current,p.status()==ExecutionStatus.NOT_STARTED?ExecutionStatus.NOT_STARTED:ExecutionStatus.STALE,
                    p.version(),null,p.startedAt(),p.completedAt()));
            current=current.next();
        }
    }

    private void submitProposalMaterialization(UUID offerId){
        Runnable task=()->documentTaskExecutor.execute(()->{
            try{proposalDocuments.materializeApprovedProposal(offerId);}
            catch(Exception ignored){/* Proposal approval remains authoritative even if rendering infrastructure is unavailable. */}
        });
        if(TransactionSynchronizationManager.isSynchronizationActive())
            TransactionSynchronizationManager.registerSynchronization(new TransactionSynchronization(){@Override public void afterCommit(){task.run();}});
        else task.run();
    }

    private void submitPhase(UUID offerId,PhaseType phaseType,String refinement){
        Runnable task=()->phaseTaskExecutor.execute(()->runPhase(offerId,phaseType,refinement));
        if(TransactionSynchronizationManager.isSynchronizationActive())
            TransactionSynchronizationManager.registerSynchronization(new TransactionSynchronization(){@Override public void afterCommit(){task.run();}});
        else task.run();
    }

    private void runPhase(UUID offerId,PhaseType phaseType,String refinement){
        try{
            var offer=find(offerId);
            switch(phaseType){
                case ANALYSIS->runAnalysis(offer,refinement);
                case STRATEGY->runStrategy(offer,refinement);
                case SOLUTION->runSolution(offer,refinement);
                case PROPOSAL->runProposal(offer,refinement);
                case SLIDE_PLAN->runSlidePlan(offer,refinement);
                case PRESENTATION->runPresentation(offer,refinement);
            }
            markWaiting(offerId,phaseType);
        }catch(Exception e){markFailed(offerId,phaseType,e);}
    }

    private void runAnalysis(Offer offer,String refinement){
        var sourceBundle=sources.loadOrIngest(offer);
        var prompt="""
                Execute the analyze-opportunity SKILL exactly, but in this call return ONLY the complete
                opportunity-brief.md as raw Markdown. Begin with its level-one heading. Do not return
                JSON, Markdown fences, questions.md or technology.md. Preserve all required sections,
                evidence locators and the distinction between bid and project execution.
                The source manifest and representations are supplied in runtime context; original
                customer evidence remains authoritative.
                """+refinement(refinement);
        var context=offerContext(offer)+"\n\n# SOURCE MANIFEST\n"+sourceBundle.manifest()+"\n\n"+sourceBundle.textualContext();
        var briefResult=agents.execute(AgentTask.of(offer.id(),PhaseType.ANALYSIS,"business-analyst","analyze-opportunity",
                "Entender y cualificar la oportunidad",prompt).withCheckpoint("analysis.opportunity-brief"),model(offer,"analysis"),context,sourceBundle.visualAttachments());
        var brief=AnalysisMarkdown.required(briefResult.content(),"opportunity-brief.md");
        var followupContext=offerContext(offer)+"\n\n# SOURCE-BASED OPPORTUNITY BRIEF (DRAFT)\n"+brief;
        var followups=agents.executeParallel(List.of(
                AgentTask.of(offer.id(),PhaseType.ANALYSIS,"business-analyst",null,
                        "Extraer preguntas de aclaración","From the supplied opportunity brief, return ONLY questions.md as raw Markdown. Start with a level-one heading and include a table with ID, Pregunta para el cliente, Motivo / impacto, Fuente, Respuesta cliente, Asunción / decisión tomada. Leave customer answers and decisions empty. Return exactly NONE when no real questions or gaps exist. Do not return JSON or fences.").withOutputFormat("optional_markdown").withCheckpoint("analysis.questions"),
                AgentTask.of(offer.id(),PhaseType.ANALYSIS,"business-analyst",null,
                        "Extraer condicionantes tecnológicos","From the supplied opportunity brief, return ONLY technology.md as raw Markdown. Start with a level-one heading and include a table with Categoría, Tecnología / producto / arquitectura, Condición o uso indicado por el cliente, Carácter, Fuente, Observaciones. Return exactly NONE when no material technology or architecture constraints exist. Do not return JSON, fences or a proposed solution.").withOutputFormat("optional_markdown").withCheckpoint("analysis.technology")
        ),model(offer,"analysis"),followupContext);
        var questions=AnalysisMarkdown.optional(followups.get(0).content(),"questions.md");
        var technology=AnalysisMarkdown.optional(followups.get(1).content(),"technology.md");
        // Publish only after all three outputs have been validated.
        saveArtifact(offer.id(),PhaseType.ANALYSIS,ArtifactType.OPPORTUNITY_BRIEF,brief);
        if(questions!=null) saveArtifact(offer.id(),PhaseType.ANALYSIS,ArtifactType.QUESTIONS,questions);
        if(technology!=null) saveArtifact(offer.id(),PhaseType.ANALYSIS,ArtifactType.TECHNOLOGY,technology);
    }

    private void runStrategy(Offer offer,String refinement){
        var context=offerContext(offer)+approvedArtifactsContext(offer.id(),List.of(ArtifactType.OPPORTUNITY_BRIEF,ArtifactType.QUESTIONS,ArtifactType.TECHNOLOGY));
        var result=agents.execute(AgentTask.of(offer.id(),PhaseType.STRATEGY,"business-analyst","build-strategy",
                "Construir estrategia de respuesta","Execute build-strategy exactly. Return only the complete strategy.md Markdown."+refinement(refinement)).withCheckpoint("strategy.document"),
                model(offer,"strategy"),context);
        saveArtifact(offer.id(),PhaseType.STRATEGY,ArtifactType.STRATEGY,result.content());
    }

    private void runSolution(Offer offer,String refinement){
        var sourceBundle=sources.loadOrIngest(offer);
        var approved=offerContext(offer)+approvedArtifactsContext(offer.id(),List.of(ArtifactType.OPPORTUNITY_BRIEF,ArtifactType.QUESTIONS,ArtifactType.TECHNOLOGY,ArtifactType.STRATEGY));

        // Triage the complete source inventory before loading expensive original evidence.
        var triageContext=approved+"\n\n# SOURCE MANIFEST\n"+sourceBundle.manifest()+refinement(refinement);
        var triage=agents.execute(AgentTask.of(offer.id(),PhaseType.SOLUTION,"solution-architect","define-solution",
                "Triage de fuentes y especialistas opcionales","""
                Before designing the solution, use the approved current-offer artifacts plus the source manifest to decide which ORIGINAL customer sources require review.
                Classify every source as REVIEW_IN_DEPTH, TARGETED_REVIEW or SKIP. Select originals whenever exact technical constraints, versions, integrations, security, data, volumes, SLAs, diagrams or other factual details may affect the solution.
                Return ONLY JSON: {"sourceReview":[{"id":"DOC-001","disposition":"REVIEW_IN_DEPTH","reason":"..."}],"specialistConsultations":[{"agentKey":"security-specialist","question":"..."}]}.
                Maximum two consultations. Do not request base roles as specialists.
                """).withOutputFormat("json").withCheckpoint("solution.triage"),model(offer,"solutionArchitecture"),triageContext);

        var selectedSources=sources.selectForSolution(sourceBundle,triage.content());
        var evidenceContext=approved+"\n\n# SOURCE MANIFEST (SELECTED ORIGINALS)\n"+selectedSources.manifest()
                +"\n\n"+selectedSources.textualContext();

        var specialistResults=runRequestedSpecialists(offer,evidenceContext,triage.content(),selectedSources.visualAttachments());

        // The architect performs one evidence-grounding pass over the authoritative originals.
        // It returns a compact internal blueprint rather than attempting the whole solution.md in one model response.
        var blueprintContext=evidenceContext+"\n\n# ARCHITECT SOURCE TRIAGE\n"+triage.content()+specialistResults;
        var blueprint=agents.execute(AgentTask.of(offer.id(),PhaseType.SOLUTION,"solution-architect",null,
                "Aterrizar blueprint técnico de la solución","""
                Execute the evidence-review and architectural reasoning needed for section A of define-solution, but DO NOT write solution.md yet.
                Produce a compact INTERNAL solution blueprint as JSON. It must preserve enough grounded detail and DOC-nnn/page/slide/sheet/section locators to draft the final document without rereading originals.
                Include: solutionSummary, principles, logicalArchitecture, components, integrations, data, security, resilience, observability, infrastructure, legacyAndTransition, decisionsAndTradeoffs, deliveryConstraints, risks, capabilityProfiles, assumptionsAndTbds, proposalHighlights, sourceReview, specialistValidations.
                Distinguish FACT, PRINCIPLE, PROPOSAL, DECISION and ASSUMPTION where material. Do not estimate effort, staffing, duration, cost or price.
                Be selective: keep the complete JSON below roughly 20,000 characters. Do not duplicate source text.
                """).withOutputFormat("json").withCheckpoint("solution.blueprint"),model(offer,"solutionArchitecture"),blueprintContext+refinement(refinement),selectedSources.visualAttachments());

        // Draft independent bounded blocks from the compact blueprint. These calls intentionally do not receive
        // the original corpus again: the preceding architect-owned blueprint is the grounded hand-off.
        var draftingContext=offerContext(offer)+"\n\n# INTERNAL SOLUTION BLUEPRINT (authoritative grounding for this draft)\n"+blueprint.content();
        var solutionPartTasks=List.of(
                solutionPartTask(offer,"Redactar solución · arquitectura base","""
                        Return ONLY JSON {"markdown":"..."} containing sections 1, 2 and 3 through subsection 3.4 of solution.md:
                        ## 1. Resumen de la solución propuesta
                        ## 2. Principios de solución
                        ## 3. Arquitectura de solución
                        ### 3.1 Arquitectura lógica
                        ### 3.2 Componentes principales
                        ### 3.3 Integraciones
                        ### 3.4 Datos
                        Preserve evidence locators and epistemic labels where material. Do not add an H1. Do not write later sections.
                        Keep this block concise and below 2,500 words.
                        """),
                solutionPartTask(offer,"Redactar solución · seguridad y operación","""
                        Return ONLY JSON {"markdown":"..."} containing exactly:
                        ### 3.5 Seguridad
                        ### 3.6 Alta disponibilidad, resiliencia y continuidad
                        ### 3.7 Observabilidad y operación
                        ### 3.8 Despliegue e infraestructura
                        ## 4. Tratamiento del legado y transición
                        Preserve evidence locators and epistemic labels where material. Do not add an H1 or repeat sections 1-3.4.
                        Keep this block concise and below 2,500 words.
                        """),
                solutionPartTask(offer,"Redactar solución · decisiones y delivery","""
                        Return ONLY JSON {"markdown":"..."} containing exactly:
                        ## 5. Decisiones técnicas y trade-offs
                        ## 6. Condicionantes de delivery
                        ## 7. Riesgos de ejecución y mitigaciones actualizadas
                        ## 8. Capacidades/perfiles necesarios a alto nivel
                        Do not estimate effort, staffing, duration, cost or price. Do not add an H1 or repeat prior sections.
                        Keep this block concise and below 2,200 words.
                        """),
                solutionPartTask(offer,"Redactar solución · cierre y trazabilidad","""
                        Return ONLY JSON {"markdown":"..."} containing exactly:
                        ## 9. Decisiones, asunciones y TBDs pendientes
                        ## 10. Elementos clave que deberán aparecer en la oferta
                        ## 11. Revisión de fuentes realizada por el arquitecto
                        ## 12. Consultas/validaciones de especialistas realizadas
                        Section 11 must account for every triaged source and preserve disposition/reason. Section 12 must faithfully reflect specialist consultations.
                        Do not add an H1 or repeat prior sections. Keep this block concise and below 2,200 words.
                        """)
        );
        var solutionParts=new ArrayList<LlmResult>();
        for(var partTask:solutionPartTasks)
            solutionParts.add(agents.execute(partTask,model(offer,"solutionArchitecture"),draftingContext));

        var solution="# Definición de solución\n\n"+String.join("\n\n",
                solutionParts.stream().map(this::markdownFromJson).toList());
        validateAssembledSolution(solution);
        saveArtifact(offer.id(),PhaseType.SOLUTION,ArtifactType.SOLUTION,solution);

        // Delivery also uses a grounding pass before the final document, so the Delivery Manager can inspect
        // authoritative originals without forcing the final delivery-plan.md call to carry the whole corpus.
        var deliveryReviewContext=evidenceContext+"\n\n# solution.md\n"+solution;
        var deliveryReview=agents.execute(AgentTask.of(offer.id(),PhaseType.SOLUTION,"delivery-manager",null,
                "Aterrizar restricciones y estrategia de delivery","""
                Review the approved solution and the selected ORIGINAL customer evidence for delivery implications. Do NOT write delivery-plan.md yet.
                Return ONLY compact JSON with: recommendedMethodology, rationale, inceptionOrDiscovery, reestimationOrDecisionGates, workstreams, milestones, dependencies, governance, customerAndThirdPartyParticipation, acceptanceAndValidation, cutoverTransitionHandover, risksAndTbds, capabilityCoverage, sourceReview.
                Preserve material evidence locators. Do not redefine the technical solution and do not estimate effort, staffing, duration, cost or price.
                Keep the JSON below roughly 16,000 characters and avoid duplicating source text.
                """).withOutputFormat("json").withCheckpoint("delivery.grounding"),model(offer,"deliveryPlanning"),deliveryReviewContext,selectedSources.visualAttachments());

        var deliveryContext=offerContext(offer)+"\n\n# solution.md\n"+solution+"\n\n# INTERNAL DELIVERY REVIEW\n"+deliveryReview.content();
        var delivery=agents.execute(AgentTask.of(offer.id(),PhaseType.SOLUTION,"delivery-manager","define-solution",
                "Definir enfoque de ejecución","""
                Execute section B of define-solution. Produce ONLY the complete unestimated delivery-plan.md as raw Markdown, without an outer code fence or filename heading.
                Use the supplied solution.md and INTERNAL DELIVERY REVIEW. Cover methodology/lifecycle, inception or discovery where appropriate, decision/re-estimation gates, workstreams, milestones, dependencies, governance, customer/third-party participation, acceptance, cutover/transition/handover, risks/TBDs and capability → workstream coverage.
                Do not redefine the technical solution. Do not estimate effort, staffing, duration, cost or price. Keep the document focused and below 4,500 words.
                """).withCheckpoint("delivery.plan"),model(offer,"deliveryPlanning"),deliveryContext);
        var deliveryPlan=delivery.content();
        saveArtifact(offer.id(),PhaseType.SOLUTION,ArtifactType.DELIVERY_PLAN,deliveryPlan);

        agents.execute(AgentTask.of(offer.id(),PhaseType.SOLUTION,"business-analyst","define-solution",
                "Revisión de coherencia","Execute section C of define-solution: review strategy, solution.md and delivery-plan.md for coherence. Do not create a canonical artifact. Return concise findings and say OK when no correction is required.").withOutputFormat("text").withCheckpoint("solution.coherence-review"),
                model(offer,"solutionArchitecture"),approved+"\n\n# solution.md\n"+solution+"\n\n# delivery-plan.md\n"+deliveryPlan);
    }

    private AgentTask solutionPartTask(Offer offer,String objective,String prompt){
        var key=switch(objective){
            case "Redactar solución · arquitectura base" -> "solution.part.architecture";
            case "Redactar solución · seguridad y operación" -> "solution.part.security-operations";
            case "Redactar solución · decisiones y delivery" -> "solution.part.decisions-delivery";
            case "Redactar solución · cierre y trazabilidad" -> "solution.part.traceability";
            default -> "solution.part."+Integer.toHexString(objective.hashCode());
        };
        return AgentTask.of(offer.id(),PhaseType.SOLUTION,"solution-architect",null,objective,prompt)
                .withOutputFormat("json").withCheckpoint(key);
    }

    private String markdownFromJson(LlmResult result){
        try{
            var markdown=json.readTree(result.content()).path("markdown").asText();
            if(markdown==null||markdown.isBlank())throw new DomainException("Solution section returned empty markdown");
            return markdown.trim();
        }catch(DomainException e){throw e;}
        catch(Exception e){throw new DomainException("Invalid structured solution section: "+e.getMessage());}
    }

    private void validateAssembledSolution(String solution){
        var required=List.of(
                "# Definición de solución",
                "## 1. Resumen de la solución propuesta",
                "## 2. Principios de solución",
                "## 3. Arquitectura de solución",
                "### 3.1 Arquitectura lógica",
                "### 3.2 Componentes principales",
                "### 3.3 Integraciones",
                "### 3.4 Datos",
                "### 3.5 Seguridad",
                "### 3.6 Alta disponibilidad, resiliencia y continuidad",
                "### 3.7 Observabilidad y operación",
                "### 3.8 Despliegue e infraestructura",
                "## 4. Tratamiento del legado y transición",
                "## 5. Decisiones técnicas y trade-offs",
                "## 6. Condicionantes de delivery",
                "## 7. Riesgos de ejecución y mitigaciones actualizadas",
                "## 8. Capacidades/perfiles necesarios a alto nivel",
                "## 9. Decisiones, asunciones y TBDs pendientes",
                "## 10. Elementos clave que deberán aparecer en la oferta",
                "## 11. Revisión de fuentes realizada por el arquitecto",
                "## 12. Consultas/validaciones de especialistas realizadas");
        var missing=required.stream().filter(h->!solution.contains(h)).toList();
        if(!missing.isEmpty())throw new DomainException("Assembled solution.md is incomplete. Missing headings: "+String.join(", ",missing));
    }

    private String runRequestedSpecialists(Offer offer,String context,String triage,List<LlmRequest.Attachment> attachments){
        try{
            JsonNode root=json.readTree(triage);
            var requested=new ArrayList<AgentTask>();
            root.path("specialistConsultations").forEach(node->{
                if(requested.size()>=2)return;
                var key=node.path("agentKey").asText(); var question=node.path("question").asText();
                try{var definition=agentRegistry.get(key);if("Specialist".equals(definition.role())) {var checkpoint="solution.specialist."+requested.size()+"."+key;requested.add(AgentTask.of(offer.id(),PhaseType.SOLUTION,key,"define-solution","Consulta especializada",question).withOutputFormat("text").withCheckpoint(checkpoint));}}catch(Exception ignored){}
            });
            if(requested.isEmpty())return "\n\n# OPTIONAL SPECIALIST CONSULTATIONS\nNone requested.";
            // Keep bounded fan-out. Specialist consultations do not own canonical artifacts.
            var results=new ArrayList<LlmResult>();
            try(var executor=java.util.concurrent.Executors.newVirtualThreadPerTaskExecutor()){
                var futures=requested.stream().map(task->java.util.concurrent.CompletableFuture.supplyAsync(()->agents.execute(task,model(offer,"specialistValidation"),context,attachments),executor)).toList();
                results.addAll(futures.stream().map(java.util.concurrent.CompletableFuture::join).toList());
            }
            var b=new StringBuilder("\n\n# OPTIONAL SPECIALIST CONSULTATIONS\n");
            for(int i=0;i<results.size();i++) b.append("\n## Consultation ").append(i+1).append("\n").append(results.get(i).content());
            return b.toString();
        }catch(Exception e){return "\n\n# OPTIONAL SPECIALIST CONSULTATIONS\nCould not parse optional consultation plan; continuing without fan-out.";}
    }

    private void runProposal(Offer offer,String refinement){
        var context=offerContext(offer)+approvedArtifactsContext(offer.id(),List.of(ArtifactType.OPPORTUNITY_BRIEF,ArtifactType.QUESTIONS,ArtifactType.TECHNOLOGY,ArtifactType.STRATEGY,ArtifactType.SOLUTION,ArtifactType.DELIVERY_PLAN));
        var result=agents.execute(AgentTask.of(offer.id(),PhaseType.PROPOSAL,"business-analyst","compose-proposal",
                "Redactar oferta detallada","Execute compose-proposal exactly. Produce ONLY the complete canonical proposal.md in Markdown. Follow PROPOSAL GUIDANCE as authoritative structure/depth guidance. Never invent prices, effort, staffing, dates, contractual commitments or customer facts."+refinement(refinement)).withCheckpoint("proposal.document"),
                model(offer,"proposal"),context+"\n\n# PROPOSAL GUIDANCE JSON\n"+proposalGuidanceJson(offer.proposalGuidance()));
        saveArtifact(offer.id(),PhaseType.PROPOSAL,ArtifactType.PROPOSAL,result.content());
    }

    private String proposalGuidanceJson(Object guidance){
        try{return json.writeValueAsString(guidance);}catch(com.fasterxml.jackson.core.JsonProcessingException e){throw new DomainException("Invalid proposal guidance");}
    }

    private void runSlidePlan(Offer offer,String refinement){
        var context=offerContext(offer)+approvedArtifactsContext(offer.id(),List.of(ArtifactType.OPPORTUNITY_BRIEF,ArtifactType.QUESTIONS,ArtifactType.TECHNOLOGY,ArtifactType.STRATEGY,ArtifactType.SOLUTION,ArtifactType.DELIVERY_PLAN,ArtifactType.PROPOSAL));
        var result=agents.execute(AgentTask.of(offer.id(),PhaseType.SLIDE_PLAN,"business-analyst","design-proposal",
                "Planificar narrativa de presentación","Execute design-proposal exactly. Produce ONLY the canonical slides-plan.md. Human presentation guidance follows in context."+refinement(refinement)).withCheckpoint("slides.plan"),
                model(offer,"slidePlanning"),context+"\n\n# PRESENTATION GUIDANCE\n"+Objects.toString(offer.presentationGuidance(),"none"));
        slidePlanValidator.validate(result.content());
        saveArtifact(offer.id(),PhaseType.SLIDE_PLAN,ArtifactType.SLIDES_PLAN,result.content());
    }

    private void runPresentation(Offer offer,String refinement){
        var plan=artifacts.findLatest(offer.id(),ArtifactType.SLIDES_PLAN).orElseThrow(()->new DomainException("Missing approved slides-plan"));
        slidePlanValidator.validate(plan.content());
        var result=presentations.materialize(offer.id(),plan.content(),offer.outputDriveFolder(),offer.presentationName());
        saveArtifact(offer.id(),PhaseType.PRESENTATION,ArtifactType.PRESENTATION_METADATA,"{\"externalId\":\""+result.externalId()+"\",\"url\":\""+result.url()+"\"}");
        saveArtifact(offer.id(),PhaseType.PRESENTATION,ArtifactType.PRESENTATION_BUILD_REPORT,result.buildReport());
    }

    private void saveArtifact(UUID offerId,PhaseType phase,ArtifactType type,String content){
        var latest=artifacts.findLatest(offerId,type);
        if(latest.isPresent()&&Objects.equals(latest.get().content(),content))return;
        artifacts.save(new Artifact(UUID.randomUUID(),offerId,phase,type,artifacts.nextVersion(offerId,type),content,Instant.now()));
    }
    private String approvedArtifactsContext(UUID offerId,List<ArtifactType> types){var b=new StringBuilder();for(var t:types)artifacts.findLatest(offerId,t).ifPresent(a->b.append("\n\n# ").append(t).append("\n").append(a.content()));return b.toString();}
    private String offerContext(Offer o){return "Offer name: %s\nOrganization: %s\nLanguage: %s\nPresentation language: %s\nGoogle Drive input folder: %s\nGoogle Drive output folder: %s\n".formatted(o.name(),o.customer(),o.language(),o.presentationLanguage(),o.inputDriveFolder(),o.outputDriveFolder());}
    private String model(Offer offer,String key){return offer.models().getOrDefault(key,"claude-sonnet-4-6");}
    private String refinement(String r){return r==null||r.isBlank()?"":"\n\n# HUMAN REFINEMENT (authoritative)\n"+r;}
    private void markWaiting(UUID offerId,PhaseType type){var p=phases.find(offerId,type).orElseThrow();phases.save(new PhaseExecution(p.id(),offerId,type,ExecutionStatus.WAITING_FOR_HUMAN,p.version(),null,p.startedAt(),Instant.now()));offers.save(copyOffer(find(offerId),type,ExecutionStatus.WAITING_FOR_HUMAN));}
    private void markFailed(UUID offerId,PhaseType type,Exception e){var p=phases.find(offerId,type).orElseThrow();phases.save(new PhaseExecution(p.id(),offerId,type,ExecutionStatus.FAILED,p.version(),e.getMessage(),p.startedAt(),Instant.now()));offers.save(copyOffer(find(offerId),type,ExecutionStatus.FAILED));}
    private Offer copyOffer(Offer o,PhaseType phase,ExecutionStatus status){return new Offer(o.id(),o.name(),o.customer(),o.language(),o.presentationLanguage(),o.inputDriveFolder(),o.outputDriveFolder(),o.presentationName(),"","",o.generatePresentation(),o.aiProvider(),o.models(),o.proposalGuidance(),o.presentationGuidance(),phase,status,o.createdAt(),Instant.now());}
    private void updateOptionalPresentationPhases(UUID offerId,boolean enabled){
        for(var type:List.of(PhaseType.SLIDE_PLAN,PhaseType.PRESENTATION)){
            var p=phases.find(offerId,type).orElseThrow();
            if(enabled&&p.status()==ExecutionStatus.CANCELLED) phases.save(new PhaseExecution(p.id(),offerId,type,ExecutionStatus.NOT_STARTED,p.version(),null,null,null));
            if(!enabled&&(p.status()==ExecutionStatus.NOT_STARTED||p.status()==ExecutionStatus.STALE)) phases.save(new PhaseExecution(p.id(),offerId,type,ExecutionStatus.CANCELLED,p.version(),null,p.startedAt(),p.completedAt()));
        }
    }
    private static String blankOr(String value,String fallback){return value==null||value.isBlank()?fallback:value.trim();}
    private void validateConfiguration(String presentationLanguage,String inputDriveFolder,String outputDriveFolder,String presentationName,boolean generatePresentation,String aiProvider,Map<String,String> models,Object proposalGuidance,Object guidance){
        var missing=new ArrayList<String>();
        if(generatePresentation&&(presentationLanguage==null||presentationLanguage.isBlank()))missing.add("idioma de presentación");
        if(inputDriveFolder==null||inputDriveFolder.isBlank())missing.add("carpeta de entrada de Google Drive");
        if(generatePresentation&&(outputDriveFolder==null||outputDriveFolder.isBlank()))missing.add("carpeta de salida de Google Drive");
        if(generatePresentation&&(presentationName==null||presentationName.isBlank()))missing.add("nombre de la presentación");
        if(aiProvider==null||aiProvider.isBlank())missing.add("proveedor de IA");
        var requiredModels=generatePresentation
                ?List.of("analysis","strategy","solutionArchitecture","deliveryPlanning","proposal","slidePlanning","presentation")
                :List.of("analysis","strategy","solutionArchitecture","deliveryPlanning","proposal");
        for(var key:requiredModels)if(models==null||models.get(key)==null||models.get(key).isBlank())missing.add("modelo IA para "+key);
        if(proposalGuidance==null)missing.add("estructura de oferta detallada");
        if(generatePresentation&&guidance==null)missing.add("estructura de presentación");
        if(!missing.isEmpty())throw new DomainException("No se puede iniciar/completar la oferta. Faltan requisitos de configuración: "+String.join(", ",missing));
    }
    private Object normalizeProposalGuidance(Object guidance){
        if(guidance instanceof Map<?,?> map && map.get("sections") instanceof Collection<?> sections && !sections.isEmpty())return guidance;
        return Map.of("sections",List.of(
                Map.of("name","Resumen ejecutivo","enabled",true,"depth","SUMMARY","guidance","Sintetizar reto, propuesta de valor y resultados esperados."),
                Map.of("name","Entendimiento del reto","enabled",true,"depth","STANDARD","guidance","Explicar contexto, necesidades y condicionantes sin inventar hechos."),
                Map.of("name","Objetivos y alcance","enabled",true,"depth","STANDARD","guidance","Cubrir objetivos, alcance, exclusiones y dependencias conocidas."),
                Map.of("name","Requisitos y condicionantes","enabled",true,"depth","DETAILED","guidance","Responder a requisitos funcionales, no funcionales y restricciones relevantes."),
                Map.of("name","Estrategia de respuesta","enabled",true,"depth","STANDARD","guidance","Conectar necesidades con la estrategia aprobada."),
                Map.of("name","Solución propuesta","enabled",true,"depth","DETAILED","guidance","Describir la solución funcional y técnica con suficiente profundidad."),
                Map.of("name","Arquitectura e integraciones","enabled",true,"depth","DETAILED","guidance","Detallar arquitectura, componentes, datos, integraciones, seguridad y operación cuando aplique."),
                Map.of("name","Enfoque de ejecución","enabled",true,"depth","DETAILED","guidance","Describir fases, workstreams, entregables, gobierno y dependencias sin inventar estimaciones."),
                Map.of("name","Calidad, riesgos y supuestos","enabled",true,"depth","STANDARD","guidance","Explicitar calidad, riesgos, mitigaciones, supuestos y cuestiones pendientes."),
                Map.of("name","Valor añadido y próximos pasos","enabled",true,"depth","STANDARD","guidance","Resumir diferenciadores sustentados y siguientes pasos.")
        ));
    }

    public record CreateOfferCommand(String name,String customer,String language,String presentationLanguage,String inputDriveFolder,String outputDriveFolder,String presentationName,boolean generatePresentation,String aiProvider,Map<String,String> models,Object proposalGuidance,Object presentationGuidance) {}
    public record UpdateOfferConfigurationCommand(String presentationLanguage,String inputDriveFolder,String outputDriveFolder,String presentationName,Boolean generatePresentation,String aiProvider,Map<String,String> models,Object proposalGuidance,Object presentationGuidance) {}

    static final class AnalysisMarkdown {
        static String required(String raw,String name){
            var content=raw==null?"":raw.trim();
            if(!content.startsWith("# ")||!content.contains("\n")||content.startsWith("# {"))
                throw new DomainException("Invalid or incomplete Markdown for "+name);
            return content;
        }
        static String optional(String raw,String name){
            if(raw!=null&&raw.trim().equals("NONE"))return null;
            return required(raw,name);
        }
    }
}
