package io.github.jaruizes.proposal.domain.model;

import java.util.List;

public record LlmRequest(
        String model,
        String systemPrompt,
        List<Message> messages,
        int maxTokens,
        List<Attachment> attachments) {

    public LlmRequest(String model, String systemPrompt, List<Message> messages, int maxTokens) {
        this(model, systemPrompt, messages, maxTokens, List.of());
    }

    public record Message(String role, String content) {}

    /** Base64 attachment sent to a multimodal model. */
    public record Attachment(String mediaType, String base64Data, String name) {}
}
