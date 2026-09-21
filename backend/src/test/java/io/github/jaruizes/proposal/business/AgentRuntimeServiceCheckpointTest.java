package io.github.jaruizes.proposal.business;

import io.github.jaruizes.proposal.domain.model.*;
import io.github.jaruizes.proposal.domain.ports.AgentExecutionRepositoryPort;
import io.github.jaruizes.proposal.domain.ports.AgentPlatformPort;
import io.micrometer.core.instrument.simple.SimpleMeterRegistry;
import io.micrometer.observation.ObservationRegistry;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.List;
import java.util.UUID;
import java.util.concurrent.atomic.AtomicInteger;

import static org.assertj.core.api.Assertions.assertThat;

class AgentRuntimeServiceCheckpointTest {

    @Test
    void reusesCompletedCheckpointOnlyWhenInputsMatch() {
        var calls=new AtomicInteger();
        AgentPlatformPort platform=(task,model,context,attachments)->{
            calls.incrementAndGet();
            return new LlmResult("{\"value\":\"ok\"}",model,120,30,"provider-"+calls.get());
        };
        var repository=new InMemoryExecutions();
        var service=new AgentRuntimeService(platform,repository,ObservationRegistry.create(),new SimpleMeterRegistry());
        var offerId=UUID.randomUUID();

        var first=AgentTask.of(offerId,PhaseType.SOLUTION,"solution-architect",null,
                "Aterrizar blueprint técnico de la solución","same prompt")
                .withOutputFormat("json").withCheckpoint("solution.blueprint");
        var firstResult=service.execute(first,"claude-sonnet-4-6","same context");

        var retry=AgentTask.of(offerId,PhaseType.SOLUTION,"solution-architect",null,
                "Aterrizar blueprint técnico de la solución","same prompt")
                .withOutputFormat("json").withCheckpoint("solution.blueprint");
        var reused=service.execute(retry,"claude-sonnet-4-6","same context");

        assertThat(calls.get()).isEqualTo(1);
        assertThat(reused.content()).isEqualTo(firstResult.content());
        assertThat(reused.inputTokens()).isZero();
        assertThat(reused.outputTokens()).isZero();
        assertThat(repository.items.stream().filter(e->e.reusedFromExecutionId()!=null)).hasSize(1);

        var changedContext=AgentTask.of(offerId,PhaseType.SOLUTION,"solution-architect",null,
                "Aterrizar blueprint técnico de la solución","same prompt")
                .withOutputFormat("json").withCheckpoint("solution.blueprint");
        service.execute(changedContext,"claude-sonnet-4-6","changed context");

        assertThat(calls.get()).isEqualTo(2);
    }

    private static final class InMemoryExecutions implements AgentExecutionRepositoryPort {
        private final List<AgentExecution> items=new ArrayList<>();

        @Override public AgentExecution save(AgentExecution execution) {
            items.removeIf(item->item.id().equals(execution.id()));
            items.add(execution);
            return execution;
        }

        @Override public List<AgentExecution> findByOfferId(UUID offerId) {
            return items.stream().filter(item->item.offerId().equals(offerId)).toList();
        }

        @Override public java.util.Optional<AgentExecution> findById(UUID id) {
            return items.stream().filter(item->item.id().equals(id)).findFirst();
        }
    }

    @Test
    void asyncTransportDispatchesAndResumesFromTerminalEvent() {
        class AsyncPlatform implements io.github.jaruizes.proposal.domain.ports.AsyncAgentPlatformPort {
            int submits;
            @Override public void submit(AgentTask task,String model,String context,List<LlmRequest.Attachment> attachments){submits++;}
            @Override public LlmResult execute(AgentTask task,String model,String context,List<LlmRequest.Attachment> attachments){
                throw new AssertionError("synchronous execute must not be used");
            }
        }
        var platform=new AsyncPlatform();
        var repository=new InMemoryExecutions();
        var service=new AgentRuntimeService(platform,repository,ObservationRegistry.create(),new SimpleMeterRegistry());
        var offerId=UUID.randomUUID();
        var task=AgentTask.of(offerId,PhaseType.PROPOSAL,"business-analyst","compose-proposal",
                "Redactar oferta detallada","compose").withCheckpoint("proposal.document");

        io.github.jaruizes.proposal.domain.exceptions.AgentExecutionDeferredException deferred=null;
        try{service.execute(task,"claude-sonnet-4-6","context");}
        catch(io.github.jaruizes.proposal.domain.exceptions.AgentExecutionDeferredException e){deferred=e;}

        assertThat(deferred).isNotNull();
        assertThat(platform.submits).isEqualTo(1);
        assertThat(repository.findById(task.id()).orElseThrow().status()).isEqualTo(AgentTaskStatus.RUNNING);

        service.completeAsync(new AgentPlatformExecutionEvent(
                task.id(),offerId,PhaseType.PROPOSAL,true,"# Proposal\nDone","claude-sonnet-4-6",
                100,20,"req-1",null));

        var retry=AgentTask.of(offerId,PhaseType.PROPOSAL,"business-analyst","compose-proposal",
                "Redactar oferta detallada","compose").withCheckpoint("proposal.document");
        var result=service.execute(retry,"claude-sonnet-4-6","context");

        assertThat(platform.submits).isEqualTo(1);
        assertThat(result.content()).contains("# Proposal");
        assertThat(result.inputTokens()).isZero();
        assertThat(result.outputTokens()).isZero();
    }

}
