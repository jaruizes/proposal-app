package io.github.jaruizes.proposal.domain.model;
import java.time.Instant; import java.util.Map; import java.util.UUID;

public record Offer(
        UUID id,
        String name,
        String customer,
        String language,
        String presentationLanguage,
        String inputDriveFolder,
        String outputDriveFolder,
        String presentationName,
        String presentationTemplateId,
        String proposalTemplateId,
        boolean generatePresentation,
        String aiProvider,
        Map<String,String> models,
        Object proposalGuidance,
        Object presentationGuidance,
        PhaseType currentPhase,
        ExecutionStatus status,
        Instant createdAt,
        Instant updatedAt) {

    public Offer(UUID id, String name, String customer, String language, String presentationLanguage,
                 String inputDriveFolder, String outputDriveFolder, String presentationName,
                 String presentationTemplateId, String proposalTemplateId, String aiProvider, Map<String,String> models,
                 Object proposalGuidance, Object presentationGuidance, PhaseType currentPhase,
                 ExecutionStatus status, Instant createdAt, Instant updatedAt) {
        this(id,name,customer,language,presentationLanguage,inputDriveFolder,outputDriveFolder,presentationName,
                presentationTemplateId,proposalTemplateId,true,aiProvider,models,proposalGuidance,presentationGuidance,
                currentPhase,status,createdAt,updatedAt);
    }

    /** Backwards-compatible constructor for code that predates proposal document templating. */
    public Offer(UUID id, String name, String customer, String language, String presentationLanguage,
                 String inputDriveFolder, String outputDriveFolder, String presentationName,
                 String presentationTemplateId, String aiProvider, Map<String,String> models,
                 Object proposalGuidance, Object presentationGuidance, PhaseType currentPhase,
                 ExecutionStatus status, Instant createdAt, Instant updatedAt) {
        this(id,name,customer,language,presentationLanguage,inputDriveFolder,outputDriveFolder,presentationName,
                presentationTemplateId,null,true,aiProvider,models,proposalGuidance,presentationGuidance,
                currentPhase,status,createdAt,updatedAt);
    }
}
