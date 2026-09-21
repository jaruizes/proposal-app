package io.github.jaruizes.proposal.domain.exceptions;

import java.util.UUID;

/**
 * Internal control-flow signal: an asynchronous Agent Platform command was dispatched
 * (or is already in-flight), so the phase must remain RUNNING until its terminal event arrives.
 */
public class AgentExecutionDeferredException extends RuntimeException {
    private final UUID executionId;

    public AgentExecutionDeferredException(UUID executionId) {
        super("Agent execution deferred: " + executionId, null, false, false);
        this.executionId = executionId;
    }

    public UUID executionId() { return executionId; }
}
