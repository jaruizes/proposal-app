package io.github.jaruizes.proposal.domain.model;
public record LlmResult(String content, String model, long inputTokens, long outputTokens, String requestId) {}
