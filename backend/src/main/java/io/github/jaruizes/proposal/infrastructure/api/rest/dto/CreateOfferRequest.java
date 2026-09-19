package io.github.jaruizes.proposal.infrastructure.api.rest.dto;
import jakarta.validation.constraints.NotBlank;
import java.util.Map;
public record CreateOfferRequest(@NotBlank String name,String customer,String language,String presentationLanguage,String inputDriveFolder,String outputDriveFolder,@NotBlank String presentationName,String presentationTemplateId,String aiProvider,Map<String,String> models,Object proposalGuidance,Object presentationGuidance) {}
