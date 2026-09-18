package io.github.jaruizes.proposal.business;

import io.github.jaruizes.proposal.domain.model.*;
import io.github.jaruizes.proposal.domain.ports.AgentExecutionRepositoryPort;
import io.github.jaruizes.proposal.domain.ports.AgentPlatformPort;
import io.micrometer.core.instrument.MeterRegistry;
import io.micrometer.core.instrument.Timer;
import io.micrometer.observation.Observation;
import io.micrometer.observation.ObservationRegistry;
import org.springframework.stereotype.Service;

import java.time.Instant;
import java.util.List;
import java.util.Locale;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;
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
        var started = Instant.now();
        var id = UUID.randomUUID();
        var observation = Observation.createNotStarted("proposal.agent.platform.execution", observationRegistry)
                .lowCardinalityKeyValue("agent", task.agentKey())
                .lowCardinalityKeyValue("skill", task.skillKey() == null ? "none" : task.skillKey())
                .lowCardinalityKeyValue("phase", task.phase().name().toLowerCase(Locale.ROOT))
                .highCardinalityKeyValue("offer.id", task.offerId().toString())
                .highCardinalityKeyValue("local.agent.execution.id", id.toString())
                .start();

        executions.save(new AgentExecution(id, task.offerId(), task.phase(), task.agentKey(), AgentTaskStatus.RUNNING,
                task.objective(), null, model, 0, 0, null, started, null, null));

        var timer = Timer.start(meterRegistry);
        try (var ignored = observation.openScope()) {
            var result = platform.execute(task, model, context, attachments);
            var completed = Instant.now();

            executions.save(new AgentExecution(id, task.offerId(), task.phase(), task.agentKey(), AgentTaskStatus.COMPLETED,
                    task.objective(), result.content(), result.model(), result.inputTokens(), result.outputTokens(),
                    result.requestId(), started, completed, null));

            meterRegistry.counter("proposal.agent.platform.requests", "agent", task.agentKey(), "status", "success").increment();
            meterRegistry.counter("proposal.agent.platform.tokens", "agent", task.agentKey(), "type", "input").increment(result.inputTokens());
            meterRegistry.counter("proposal.agent.platform.tokens", "agent", task.agentKey(), "type", "output").increment(result.outputTokens());
            timer.stop(Timer.builder("proposal.agent.platform.duration")
                    .tag("agent", task.agentKey()).tag("phase", task.phase().name().toLowerCase(Locale.ROOT))
                    .tag("status", "success").register(meterRegistry));
            return result;
        } catch (RuntimeException ex) {
            var completed = Instant.now();
            observation.error(ex);
            executions.save(new AgentExecution(id, task.offerId(), task.phase(), task.agentKey(), AgentTaskStatus.FAILED,
                    task.objective(), null, model, 0, 0, null, started, completed, ex.getMessage()));
            meterRegistry.counter("proposal.agent.platform.requests", "agent", task.agentKey(), "status", "error").increment();
            timer.stop(Timer.builder("proposal.agent.platform.duration")
                    .tag("agent", task.agentKey()).tag("phase", task.phase().name().toLowerCase(Locale.ROOT))
                    .tag("status", "error").register(meterRegistry));
            throw ex;
        } finally {
            observation.stop();
        }
    }

    public List<LlmResult> executeParallel(List<AgentTask> tasks, String model, String context) {
        try (var executor = Executors.newVirtualThreadPerTaskExecutor()) {
            var futures = tasks.stream()
                    .map(task -> CompletableFuture.supplyAsync(() -> execute(task, model, context), executor))
                    .toList();
            return futures.stream().map(CompletableFuture::join).toList();
        }
    }
}
