package io.github.jaruizes.proposal.infrastructure.persistence.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

import java.time.Instant;
import java.util.UUID;

@Entity
@Table(name = "offers")
public class OfferJpaEntity {
    @Id
    private UUID id;
    private String name;
    private String customer;
    private String language;
    @Column(name = "presentation_language")
    private String presentationLanguage;
    @Column(name = "input_drive_folder")
    private String inputDriveFolder;
    @Column(name = "output_drive_folder")
    private String outputDriveFolder;
    @Column(name = "presentation_name")
    private String presentationName;
    @Column(name = "presentation_template_id")
    private String presentationTemplateId;
    @Column(name = "ai_provider")
    private String aiProvider;
    @Column(name = "models_json", columnDefinition = "text")
    private String modelsJson;
    @Column(name = "presentation_guidance_json", columnDefinition = "text")
    private String presentationGuidanceJson;
    @Column(name = "current_phase")
    private String currentPhase;
    private String status;
    @Column(name = "created_at")
    private Instant createdAt;
    @Column(name = "updated_at")
    private Instant updatedAt;

    public OfferJpaEntity() {}

    public UUID getId() { return id; }
    public void setId(UUID id) { this.id = id; }
    public String getName() { return name; }
    public void setName(String name) { this.name = name; }
    public String getCustomer() { return customer; }
    public void setCustomer(String customer) { this.customer = customer; }
    public String getLanguage() { return language; }
    public void setLanguage(String language) { this.language = language; }
    public String getPresentationLanguage() { return presentationLanguage; }
    public void setPresentationLanguage(String presentationLanguage) { this.presentationLanguage = presentationLanguage; }
    public String getInputDriveFolder() { return inputDriveFolder; }
    public void setInputDriveFolder(String inputDriveFolder) { this.inputDriveFolder = inputDriveFolder; }
    public String getOutputDriveFolder() { return outputDriveFolder; }
    public void setOutputDriveFolder(String outputDriveFolder) { this.outputDriveFolder = outputDriveFolder; }
    public String getPresentationName() { return presentationName; }
    public void setPresentationName(String presentationName) { this.presentationName = presentationName; }
    public String getPresentationTemplateId() { return presentationTemplateId; }
    public void setPresentationTemplateId(String presentationTemplateId) { this.presentationTemplateId = presentationTemplateId; }
    public String getAiProvider() { return aiProvider; }
    public void setAiProvider(String aiProvider) { this.aiProvider = aiProvider; }
    public String getModelsJson() { return modelsJson; }
    public void setModelsJson(String modelsJson) { this.modelsJson = modelsJson; }
    public String getPresentationGuidanceJson() { return presentationGuidanceJson; }
    public void setPresentationGuidanceJson(String presentationGuidanceJson) { this.presentationGuidanceJson = presentationGuidanceJson; }
    public String getCurrentPhase() { return currentPhase; }
    public void setCurrentPhase(String currentPhase) { this.currentPhase = currentPhase; }
    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }
    public Instant getCreatedAt() { return createdAt; }
    public void setCreatedAt(Instant createdAt) { this.createdAt = createdAt; }
    public Instant getUpdatedAt() { return updatedAt; }
    public void setUpdatedAt(Instant updatedAt) { this.updatedAt = updatedAt; }
}
