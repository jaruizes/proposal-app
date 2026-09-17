package io.github.jaruizes.proposal.domain.ports;

import io.github.jaruizes.proposal.domain.model.LlmRequest;

import java.util.List;
import java.util.UUID;

public interface PresentationPort {
    String inspectTemplate();
    PresentationResult materialize(UUID offerId, String slidesPlan, String outputFolder, String documentName, String operationPlan);
    PresentationInspection inspectGenerated(String presentationId);
    void applyOperations(String presentationId, String operationPlan);

    record PresentationResult(String externalId, String url, String buildReport) {}
    record PresentationInspection(String structure, List<LlmRequest.Attachment> thumbnails) {}
}
