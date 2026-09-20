package io.github.jaruizes.proposal.domain.model;

public record RenderedDocument(
        byte[] content,
        String mediaType,
        String fileName,
        String templateId,
        String rendererVersion) {}
