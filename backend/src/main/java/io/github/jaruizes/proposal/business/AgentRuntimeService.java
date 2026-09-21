package io.github.jaruizes.proposal.business;

import io.github.jaruizes.proposal.domain.exceptions.AgentExecutionDeferredException;
import io.github.jaruizes.proposal.domain.model.*;
import io.github.jaruizes.proposal.domain.ports.AgentExecutionRepositoryPort;
import io.github.jaruizes.proposal.domain.ports.AgentPlatformPort;
import io.github.jaruizes.proposal.domain.ports.AsyncAgentPlatformPort;
import io.micrometer.core.instrument.MeterRegistry;
import io.micrometer.core.instrument.Timer;
import io.micrometer.observation.Observation;
import io.micrometer.observation.ObservationRegistry;
import org.springframework.stereotype.Service;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.Instant;
import java.util.Comparator;
import java.util.HexFormat;
import java.util.List;
import java.util.Locale;
import java.util.Objects;
import java.util.TreeMap;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.CompletionException;
import java.util.concurrent.Executors;

@Service
public class AgentRuntimeService {
    private final AgentPlatformPort platform;
    private final AgentExecutionRepositoryPort executions;
    private final ObservationRegistry observationRegistry;
    private final MeterRegistry meterRegistry;

    public AgentRuntimeService(AgentPlatformPort platform,
                               AgentExecutionRepositoryPort executions,
                               ObservationRegistry observationRegistry,
                               MeterRegistry meterRegistry) {
        this.platform = platform;
        this.executions = executions;
        this.observationRegistry = observationRegistry;
        this.meterRegistry = meterRegistry;
    }

    public LlmResult execute(AgentTask task, String model, String context) {
        return execute(task, model, context, List.of());
    }

    public LlmResult execute(AgentTask task, String model, String context, List<LlmRequest.Attachment> attachments) {
        var explicitCheckpointKey=blankToNull(task.checkpointKey());
        final String checkpointKey=(explicitCheckpointKey==null && platform instanceof AsyncAgentPlatformPort)
                ?"auto:"+task.phase().name().toLowerCase(Locale.ROOT)+":"+task.agentKey()+":"+task.objective()
                :explicitCheckpointKey;
        final String fingerprint=checkpointKey==null?null:fingerprint(task,model,context,attachments);

        if(checkpointKey!=null){
            var candidates=executions.findByOfferId(task.offerId()).stream()
                    .filter(e->e.phase()==task.phase())
                    .filter(e->Objects.equals(e.agentKey(),task.agentKey()))
                    .filter(e->Objects.equals(e.checkpointKey(),checkpointKey))
                    .filter(e->Objects.equals(e.inputFingerprint(),fingerprint))
                    .toList();

            var reusable=candidates.stream()
                    .filter(e->e.status()==AgentTaskStatus.COMPLETED)
                    .filter(e->e.output()!=null)
                    .max(Comparator.comparing(AgentExecution::completedAt,Comparator.nullsLast(Comparator.naturalOrder())));
            if(reusable.isPresent()){
                var source=reusable.get();
                var now=Instant.now();
                var reused=new AgentExecution(task.id(),task.offerId(),task.phase(),task.agentKey(),AgentTaskStatus.COMPLETED,
                        task.objective(),source.output(),source.model(),0,0,
                        "reused:"+source.id(),now,now,null,checkpointKey,fingerprint,source.id());
                executions.save(reused);
                meterRegistry.counter("proposal.agent.platform.requests","agent",task.agentKey(),"status","reused").increment();
                return new LlmResult(source.output(),source.model()==null?model:source.model(),0,0,reused.providerRequestId());
            }

            var inFlight=candidates.stream()
                    .filter(e->e.status()==AgentTaskStatus.RUNNING)
                    .max(Comparator.comparing(AgentExecution::startedAt,Comparator.nullsLast(Comparator.naturalOrder())));
            if(inFlight.isPresent() && platform instanceof AsyncAgentPlatformPort){
                throw new AgentExecutionDeferredException(inFlight.get().id());
            }
        }

        if(platform instanceof AsyncAgentPlatformPort asyncPlatform){
            return dispatchAsync(task,model,context,attachments,checkpointKey,fingerprint,asyncPlatform);
        }
        return executeSynchronously(task,model,context,attachments,checkpointKey,fingerprint);
    }

    private LlmResult dispatchAsync(AgentTask task,String model,String context,List<LlmRequest.Attachment> attachments,
                                    String checkpointKey,String fingerprint,AsyncAgentPlatformPort asyncPlatform){
        var started=Instant.now();
        executions.save(new AgentExecution(task.id(),task.offerId(),task.phase(),task.agentKey(),AgentTaskStatus.RUNNING,
                task.objective(),null,model,0,0,null,started,null,null,checkpointKey,fingerprint,null));
        try{
            asyncPlatform.submit(task,model,context,attachments);
            meterRegistry.counter("proposal.agent.platform.requests","agent",task.agentKey(),"status","dispatched").increment();
            throw new AgentExecutionDeferredException(task.id());
        }catch(AgentExecutionDeferredException e){
            throw e;
        }catch(RuntimeException ex){
            var completed=Instant.now();
            executions.save(new AgentExecution(task.id(),task.offerId(),task.phase(),task.agentKey(),AgentTaskStatus.FAILED,
                    task.objective(),null,model,0,0,null,started,completed,ex.getMessage(),checkpointKey,fingerprint,null));
            meterRegistry.counter("proposal.agent.platform.requests","agent",task.agentKey(),"status","dispatch_error").increment();
            throw ex;
        }
    }

    private LlmResult executeSynchronously(AgentTask task,String model,String context,List<LlmRequest.Attachment> attachments,
                                           String checkpointKey,String fingerprint){
        var started = Instant.now();
        var id = task.id();
        var observation = Observation.createNotStarted("proposal.agent.platform.execution", observationRegistry)
                .lowCardinalityKeyValue("agent", task.agentKey())
                .lowCardinalityKeyValue("skill", task.skillKey() == null ? "none" : task.skillKey())
                .lowCardinalityKeyValue("phase", task.phase().name().toLowerCase(Locale.ROOT))
                .highCardinalityKeyValue("offer.id", task.offerId().toString())
                .highCardinalityKeyValue("agent.execution.id", id.toString())
                .start();

        executions.save(new AgentExecution(id, task.offerId(), task.phase(), task.agentKey(), AgentTaskStatus.RUNNING,
                task.objective(), null, model, 0, 0, null, started, null, null,checkpointKey,fingerprint,null));

        var timer = Timer.start(meterRegistry);
        try (var ignored = observation.openScope()) {
            var result = platform.execute(task, model, context, attachments);
            var completed = Instant.now();

            executions.save(new AgentExecution(id, task.offerId(), task.phase(), task.agentKey(), AgentTaskStatus.COMPLETED,
                    task.objective(), result.content(), result.model(), result.inputTokens(), result.outputTokens(),
                    result.requestId(), started, completed, null,checkpointKey,fingerprint,null));

            recordUsage(task,result);
            timer.stop(Timer.builder("proposal.agent.platform.duration")
                    .tag("agent", task.agentKey()).tag("phase", task.phase().name().toLowerCase(Locale.ROOT))
                    .tag("status", "success").register(meterRegistry));
            return result;
        } catch (RuntimeException ex) {
            var completed = Instant.now();
            observation.error(ex);
            executions.save(new AgentExecution(id, task.offerId(), task.phase(), task.agentKey(), AgentTaskStatus.FAILED,
                    task.objective(), null, model, 0, 0, null, started, completed, ex.getMessage(),checkpointKey,fingerprint,null));
            meterRegistry.counter("proposal.agent.platform.requests", "agent", task.agentKey(), "status", "error").increment();
            timer.stop(Timer.builder("proposal.agent.platform.duration")
                    .tag("agent", task.agentKey()).tag("phase", task.phase().name().toLowerCase(Locale.ROOT))
                    .tag("status", "error").register(meterRegistry));
            throw ex;
        } finally {
            observation.stop();
        }
    }

    /**
     * Applies a terminal event to the local durable execution record.
     * Returns the updated execution, or null when the event is duplicate/unknown.
     */
    public AgentExecution completeAsync(AgentPlatformExecutionEvent event){
        var current=executions.findById(event.executionId()).orElse(null);
        if(current==null || current.status()!=AgentTaskStatus.RUNNING) return null;
        var completedAt=Instant.now();
        var status=event.completed()?AgentTaskStatus.COMPLETED:AgentTaskStatus.FAILED;
        var updated=new AgentExecution(
                current.id(),current.offerId(),current.phase(),current.agentKey(),status,current.objective(),
                event.completed()?event.content():null,
                event.model()==null?current.model():event.model(),
                event.inputTokens(),event.outputTokens(),event.providerRequestId(),
                current.startedAt(),completedAt,event.completed()?null:event.errorMessage(),
                current.checkpointKey(),current.inputFingerprint(),current.reusedFromExecutionId());
        executions.save(updated);
        if(event.completed()){
            var result=new LlmResult(updated.output(),updated.model(),updated.inputTokens(),updated.outputTokens(),updated.providerRequestId());
            recordUsage(new AgentTask(updated.id(),updated.offerId(),updated.phase(),updated.agentKey(),null,updated.objective(),null,java.util.Map.of()),result);
        }else{
            meterRegistry.counter("proposal.agent.platform.requests","agent",updated.agentKey(),"status","error").increment();
        }
        return updated;
    }

    public List<LlmResult> executeParallel(List<AgentTask> tasks, String model, String context) {
        try (var executor = Executors.newVirtualThreadPerTaskExecutor()) {
            var futures = tasks.stream()
                    .map(task -> CompletableFuture.supplyAsync(() -> execute(task, model, context), executor))
                    .toList();
            var results=new java.util.ArrayList<LlmResult>();
            AgentExecutionDeferredException deferred=null;
            for(var future:futures){
                try{
                    results.add(future.join());
                }catch(CompletionException ex){
                    var cause=ex.getCause();
                    if(cause instanceof AgentExecutionDeferredException d){
                        deferred=d;
                    }else if(cause instanceof RuntimeException runtime){
                        throw runtime;
                    }else{
                        throw ex;
                    }
                }
            }
            if(deferred!=null) throw deferred;
            return results;
        }
    }

    private void recordUsage(AgentTask task,LlmResult result){
        meterRegistry.counter("proposal.agent.platform.requests", "agent", task.agentKey(), "status", "success").increment();
        meterRegistry.counter("proposal.agent.platform.tokens", "agent", task.agentKey(), "type", "input").increment(result.inputTokens());
        meterRegistry.counter("proposal.agent.platform.tokens", "agent", task.agentKey(), "type", "output").increment(result.outputTokens());
    }

    private static String fingerprint(AgentTask task,String model,String context,List<LlmRequest.Attachment> attachments){
        try{
            var digest=MessageDigest.getInstance("SHA-256");
            update(digest,task.agentKey());update(digest,task.skillKey());update(digest,task.objective());update(digest,task.prompt());
            update(digest,model);update(digest,context);update(digest,new TreeMap<>(task.metadata()).toString());
            for(var attachment:attachments){
                update(digest,attachment.name());update(digest,attachment.mediaType());update(digest,attachment.base64Data());
            }
            return HexFormat.of().formatHex(digest.digest());
        }catch(Exception e){
            throw new IllegalStateException("Cannot fingerprint agent checkpoint",e);
        }
    }

    private static void update(MessageDigest digest,String value){
        digest.update(Objects.toString(value,"").getBytes(StandardCharsets.UTF_8));
        digest.update((byte)0);
    }

    private static String blankToNull(String value){
        return value==null||value.isBlank()?null:value;
    }
}
