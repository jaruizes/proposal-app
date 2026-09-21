package io.github.jaruizes.proposal.domain.model;

import java.util.Map;

/** Process-agnostic artifact returned by Agent Platform. */
public record AgentPlatformArtifact(
        String type,
        String name,
        String mediaType,
        String content,
        String uri,
        Map<String,Object> metadata) {

    public boolean hasInlineContent() {
        return content != null && !content.isBlank();
    }

    public boolean hasReference() {
        return uri != null && !uri.isBlank();
    }
}
