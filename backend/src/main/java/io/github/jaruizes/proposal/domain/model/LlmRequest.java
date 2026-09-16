package io.github.jaruizes.proposal.domain.model;
import java.util.List;
public record LlmRequest(String model, String systemPrompt, List<Message> messages, int maxTokens) { public record Message(String role, String content) {} }
