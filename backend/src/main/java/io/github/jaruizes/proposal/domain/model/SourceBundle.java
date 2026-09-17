package io.github.jaruizes.proposal.domain.model;

import java.util.List;

/** Prepared source corpus used by one isolated agent execution context. */
public record SourceBundle(
        String manifest,
        String textualContext,
        List<LlmRequest.Attachment> visualAttachments,
        String ingestionReport) {
    public SourceBundle {
        visualAttachments = visualAttachments == null ? List.of() : List.copyOf(visualAttachments);
    }
}
