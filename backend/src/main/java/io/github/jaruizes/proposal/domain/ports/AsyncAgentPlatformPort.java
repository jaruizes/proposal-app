package io.github.jaruizes.proposal.domain.ports;

import io.github.jaruizes.proposal.domain.model.AgentTask;
import io.github.jaruizes.proposal.domain.model.LlmRequest;

import java.util.List;

/**
 * Command-side contract for transports where execution completion arrives later as an event.
 */
public interface AsyncAgentPlatformPort extends AgentPlatformPort {
    void submit(AgentTask task, String model, String context, List<LlmRequest.Attachment> attachments);
}
