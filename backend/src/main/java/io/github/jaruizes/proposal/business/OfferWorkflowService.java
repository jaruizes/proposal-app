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
    private final ObjectMapper json = new ObjectMapper();

    public OfferWorkflowService(OfferRepositoryPort offers, PhaseRepositoryPort phases,
                                ArtifactRepositoryPort artifacts, AgentExecutionRepositoryPort agentExecutions,
                                AgentRuntimeService agents, AgentRegistryService agentRegistry,
                                SourceIngestionService sources, PresentationPort presentations,
                                SlidePlanValidator slidePlanValidator,
                                @Qualifier("agentTaskExecutor") TaskExecutor phaseTaskExecutor) {
        this.offers=offers; this.phases=phases; this.artifacts=artifacts; this.agentExecutions=agentExecutions;
        this.agents=agents; this.agentRegistry=agentRegistry; this.sources=sources; this.presentations=presentations;
        this.slidePlanValidator=slidePlanValidator; this.phaseTaskExecutor=phaseTaskExecutor;
    }

    @Transactional
    public Offer create(CreateOfferCommand command) {
        var now=Instant.now();
        var offer=new Offer(UUID.randomUUID(),command.name(),command.customer(),command.language(),command.presentationLanguage(),
                command.inputDriveFolder(),command.outputDriveFolder(),command.presentationName(),command.aiProvider(),
                command.models(),command.presentationGuidance(),PhaseType.ANALYSIS,ExecutionStatus.RUNNING,now,now);
        offer=offers.save(offer);
        for(var phase:PhaseType.values()) phases.save(new PhaseExecution(UUID.randomUUID(),offer.id(),phase,
                phase==PhaseType.ANALYSIS?ExecutionStatus.RUNNING:ExecutionStatus.NOT_STARTED,1,null,
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
        var offer=find(offerId); var next=phaseType.next();
        if(next==null){offers.save(copyOffer(offer,phaseType,ExecutionStatus.APPROVED));return;}
        var n=phases.find(offerId,next).orElseThrow();
        phases.save(new PhaseExecution(n.id(),offerId,next,ExecutionStatus.RUNNING,n.version(),null,Instant.now(),null));
        offers.save(copyOffer(offer,next,ExecutionStatus.RUNNING));
        submitPhase(offerId,next,null);
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
                case SLIDE_PLAN->runSlidePlan(offer,refinement);
                case PRESENTATION->runPresentation(offer,refinement);
            }
            markWaiting(offerId,phaseType);
        }catch(Exception e){markFailed(offerId,phaseType,e);}
    }

    private void runAnalysis(Offer offer,String refinement){
        var sourceBundle=sources.loadOrIngest(offer);
        var prompt="""
                Execute the analyze-opportunity SKILL exactly. Produce the canonical phase outputs, but return them in ONE machine-readable JSON envelope so the platform can persist them safely:
                {"opportunityBrief":"<complete opportunity-brief.md>","questions":"<complete questions.md or null>","technology":"<complete technology.md or null>"}
                Do not wrap the JSON in Markdown fences. The source manifest and representations are supplied in runtime context; original customer evidence remains authoritative.
                """+refinement(refinement);
        var context=offerContext(offer)+"\n\n# SOURCE MANIFEST\n"+sourceBundle.manifest()+"\n\n"+sourceBundle.textualContext();
        var result=agents.execute(AgentTask.of(offer.id(),PhaseType.ANALYSIS,"business-analyst","analyze-opportunity",
                "Entender y cualificar la oportunidad",prompt),model(offer,"analysis"),context,sourceBundle.visualAttachments());
        var parsed=JsonFragments.parse(result.content());
        saveArtifact(offer.id(),PhaseType.ANALYSIS,ArtifactType.OPPORTUNITY_BRIEF,parsed.getOrDefault("opportunityBrief",result.content()));
        if(parsed.get("questions")!=null&&!parsed.get("questions").isBlank()) saveArtifact(offer.id(),PhaseType.ANALYSIS,ArtifactType.QUESTIONS,parsed.get("questions"));
        if(parsed.get("technology")!=null&&!parsed.get("technology").isBlank()) saveArtifact(offer.id(),PhaseType.ANALYSIS,ArtifactType.TECHNOLOGY,parsed.get("technology"));
    }

    private void runStrategy(Offer offer,String refinement){
        var context=offerContext(offer)+approvedArtifactsContext(offer.id(),List.of(ArtifactType.OPPORTUNITY_BRIEF,ArtifactType.QUESTIONS,ArtifactType.TECHNOLOGY));
        var result=agents.execute(AgentTask.of(offer.id(),PhaseType.STRATEGY,"business-analyst","build-strategy",
                "Construir estrategia de respuesta","Execute build-strategy exactly. Return only the complete strategy.md Markdown."+refinement(refinement)),
                model(offer,"strategy"),context);
        saveArtifact(offer.id(),PhaseType.STRATEGY,ArtifactType.STRATEGY,result.content());
    }

    private void runSolution(Offer offer,String refinement){
        var sourceBundle=sources.loadOrIngest(offer);
        var base=offerContext(offer)+approvedArtifactsContext(offer.id(),List.of(ArtifactType.OPPORTUNITY_BRIEF,ArtifactType.QUESTIONS,ArtifactType.TECHNOLOGY,ArtifactType.STRATEGY))
                +"\n\n# SOURCE MANIFEST\n"+sourceBundle.manifest()+"\n\n"+sourceBundle.textualContext();

        // Dedicated architect context first performs source triage and may request at most two bounded optional consultations.
        var triage=agents.execute(AgentTask.of(offer.id(),PhaseType.SOLUTION,"solution-architect","define-solution",
                "Triage de fuentes y especialistas opcionales","""
                Before writing solution.md, triage every source as REVIEW_IN_DEPTH, TARGETED_REVIEW or SKIP and decide whether bounded specialist consultations are genuinely needed.
                Return ONLY JSON: {"sourceReview":[{"id":"DOC-001","disposition":"REVIEW_IN_DEPTH","reason":"..."}],"specialistConsultations":[{"agentKey":"security-specialist","question":"..."}]}.
                Maximum two consultations. Do not request base roles as specialists.
                """),model(offer,"solutionArchitecture"),base,sourceBundle.visualAttachments());

        var specialistResults=runRequestedSpecialists(offer,base,triage.content(),sourceBundle.visualAttachments());
        var architectContext=base+"\n\n# ARCHITECT SOURCE TRIAGE\n"+triage.content()+specialistResults;
        var architect=agents.execute(AgentTask.of(offer.id(),PhaseType.SOLUTION,"solution-architect","define-solution",
                "Definir solución propuesta","Execute section A of define-solution. Produce ONLY the complete solution.md, including source review and any specialist consultations. Do not estimate effort, duration, staffing, cost or price."+refinement(refinement)),
                model(offer,"solutionArchitecture"),architectContext,sourceBundle.visualAttachments());
        saveArtifact(offer.id(),PhaseType.SOLUTION,ArtifactType.SOLUTION,architect.content());

        // Delivery is deliberately sequential and consumes the architect artifact in its own isolated role context.
        var deliveryContext=base+"\n\n# solution.md\n"+architect.content();
        var delivery=agents.execute(AgentTask.of(offer.id(),PhaseType.SOLUTION,"delivery-manager","define-solution",
                "Definir enfoque de ejecución","Execute section B of define-solution. Produce ONLY the complete unestimated solution-plan.md. Include capability → workstream coverage."),
                model(offer,"deliveryPlanning"),deliveryContext,sourceBundle.visualAttachments());
        saveArtifact(offer.id(),PhaseType.SOLUTION,ArtifactType.SOLUTION_PLAN,delivery.content());

        agents.execute(AgentTask.of(offer.id(),PhaseType.SOLUTION,"business-analyst","define-solution",
                "Revisión de coherencia","Execute section C of define-solution: review strategy, solution.md and solution-plan.md for coherence. Do not create a canonical artifact. Return concise findings and say OK when no correction is required."),
                model(offer,"solutionArchitecture"),base+"\n\n# solution.md\n"+architect.content()+"\n\n# solution-plan.md\n"+delivery.content());
    }

    private String runRequestedSpecialists(Offer offer,String context,String triage,List<LlmRequest.Attachment> attachments){
        try{
            JsonNode root=json.readTree(stripFences(triage));
            var requested=new ArrayList<AgentTask>();
            root.path("specialistConsultations").forEach(node->{
                if(requested.size()>=2)return;
                var key=node.path("agentKey").asText(); var question=node.path("question").asText();
                try{var definition=agentRegistry.get(key);if("Specialist".equals(definition.role())) requested.add(AgentTask.of(offer.id(),PhaseType.SOLUTION,key,"define-solution","Consulta especializada",question));}catch(Exception ignored){}
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

    private void runSlidePlan(Offer offer,String refinement){
        var context=offerContext(offer)+approvedArtifactsContext(offer.id(),List.of(ArtifactType.OPPORTUNITY_BRIEF,ArtifactType.QUESTIONS,ArtifactType.TECHNOLOGY,ArtifactType.STRATEGY,ArtifactType.SOLUTION,ArtifactType.SOLUTION_PLAN));
        var result=agents.execute(AgentTask.of(offer.id(),PhaseType.SLIDE_PLAN,"business-analyst","design-proposal",
                "Planificar narrativa de presentación","Execute design-proposal exactly. Produce ONLY the canonical slides-plan.md. Human presentation guidance follows in context."+refinement(refinement)),
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
        artifacts.save(new Artifact(UUID.randomUUID(),offerId,phase,type,artifacts.nextVersion(offerId,type),content,Instant.now()));
    }
    private String approvedArtifactsContext(UUID offerId,List<ArtifactType> types){var b=new StringBuilder();for(var t:types)artifacts.findLatest(offerId,t).ifPresent(a->b.append("\n\n# ").append(t).append("\n").append(a.content()));return b.toString();}
    private String offerContext(Offer o){return "Offer name: %s\nOrganization: %s\nLanguage: %s\nPresentation language: %s\nGoogle Drive input folder: %s\nGoogle Drive output folder: %s\n".formatted(o.name(),o.customer(),o.language(),o.presentationLanguage(),o.inputDriveFolder(),o.outputDriveFolder());}
    private String model(Offer offer,String key){return offer.models().getOrDefault(key,"claude-sonnet-4-6");}
    private String refinement(String r){return r==null||r.isBlank()?"":"\n\n# HUMAN REFINEMENT (authoritative)\n"+r;}
    private void markWaiting(UUID offerId,PhaseType type){var p=phases.find(offerId,type).orElseThrow();phases.save(new PhaseExecution(p.id(),offerId,type,ExecutionStatus.WAITING_FOR_HUMAN,p.version(),null,p.startedAt(),Instant.now()));offers.save(copyOffer(find(offerId),type,ExecutionStatus.WAITING_FOR_HUMAN));}
    private void markFailed(UUID offerId,PhaseType type,Exception e){var p=phases.find(offerId,type).orElseThrow();phases.save(new PhaseExecution(p.id(),offerId,type,ExecutionStatus.FAILED,p.version(),e.getMessage(),p.startedAt(),Instant.now()));offers.save(copyOffer(find(offerId),type,ExecutionStatus.FAILED));}
    private Offer copyOffer(Offer o,PhaseType phase,ExecutionStatus status){return new Offer(o.id(),o.name(),o.customer(),o.language(),o.presentationLanguage(),o.inputDriveFolder(),o.outputDriveFolder(),o.presentationName(),o.aiProvider(),o.models(),o.presentationGuidance(),phase,status,o.createdAt(),Instant.now());}
    private static String stripFences(String raw){var s=raw.trim();if(s.startsWith("```")){var first=s.indexOf('\n');var last=s.lastIndexOf("```");if(first>=0&&last>first)s=s.substring(first+1,last).trim();}return s;}

    public record CreateOfferCommand(String name,String customer,String language,String presentationLanguage,String inputDriveFolder,String outputDriveFolder,String presentationName,String aiProvider,Map<String,String> models,Object presentationGuidance) {}

    static final class JsonFragments {
        private static final ObjectMapper MAPPER=new ObjectMapper();
        static Map<String,String> parse(String raw){
            try{var node=MAPPER.readTree(stripFences(raw));var out=new HashMap<String,String>();for(var key:List.of("opportunityBrief","questions","technology"))if(node.hasNonNull(key))out.put(key,node.get(key).asText());return out;}
            catch(Exception e){return Map.of("opportunityBrief",raw);}
        }
    }
}
