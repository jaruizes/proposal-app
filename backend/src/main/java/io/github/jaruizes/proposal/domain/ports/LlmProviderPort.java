package io.github.jaruizes.proposal.domain.ports;
import io.github.jaruizes.proposal.domain.model.*;
public interface LlmProviderPort { LlmResult execute(LlmRequest request); }
