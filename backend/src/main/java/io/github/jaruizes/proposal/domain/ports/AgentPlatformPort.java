package io.github.jaruizes.proposal.domain.ports;

import io.github.jaruizes.proposal.domain.model.AgentTask;
import io.github.jaruizes.proposal.domain.model.LlmRequest;
import io.github.jaruizes.proposal.domain.model.LlmResult;

import java.util.List;

public interface AgentPlatformPort {
    LlmResult execute(AgentTask task, String model, String context, List<LlmRequest.Attachment> attachments);
}
