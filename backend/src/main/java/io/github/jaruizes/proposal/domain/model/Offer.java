package io.github.jaruizes.proposal.domain.model;
import java.time.Instant; import java.util.Map; import java.util.UUID;
public record Offer(UUID id, String name, String customer, String language, String presentationLanguage, String inputDriveFolder, String outputDriveFolder, String presentationName, String presentationTemplateId, String aiProvider, Map<String,String> models, Object presentationGuidance, PhaseType currentPhase, ExecutionStatus status, Instant createdAt, Instant updatedAt) {}
