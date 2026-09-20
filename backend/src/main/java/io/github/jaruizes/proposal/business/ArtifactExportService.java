package io.github.jaruizes.proposal.business;

import io.github.jaruizes.proposal.domain.exceptions.DomainException;
import io.github.jaruizes.proposal.domain.model.ArtifactType;
import io.github.jaruizes.proposal.domain.model.DocumentRenderRequest;
import io.github.jaruizes.proposal.domain.model.RenderedDocument;
import io.github.jaruizes.proposal.domain.ports.ArtifactRepositoryPort;
import io.github.jaruizes.proposal.domain.ports.DocumentPort;
import io.github.jaruizes.proposal.domain.ports.OfferRepositoryPort;
import org.springframework.stereotype.Service;

import java.util.Map;
import java.util.Set;
import java.util.UUID;

@Service
public class ArtifactExportService {
    private static final Set<ArtifactType> MARKDOWN_TYPES = Set.of(
            ArtifactType.OPPORTUNITY_BRIEF,
            ArtifactType.QUESTIONS,
            ArtifactType.TECHNOLOGY,
            ArtifactType.STRATEGY,
            ArtifactType.SOLUTION,
            ArtifactType.SOLUTION_PLAN,
            ArtifactType.PROPOSAL,
            ArtifactType.SLIDES_PLAN);

    private final OfferRepositoryPort offers;
    private final ArtifactRepositoryPort artifacts;
    private final DocumentPort documents;

    public ArtifactExportService(OfferRepositoryPort offers, ArtifactRepositoryPort artifacts, DocumentPort documents) {
        this.offers = offers;
        this.artifacts = artifacts;
        this.documents = documents;
    }

    public RenderedDocument exportPdf(UUID offerId, ArtifactType type, int version) {
        if (!MARKDOWN_TYPES.contains(type)) {
            throw new DomainException("Artifact type " + type + " cannot be exported as Markdown PDF");
        }
        var offer = offers.findById(offerId).orElseThrow(() -> new DomainException("Offer not found"));
        var artifact = artifacts.findByOfferId(offerId).stream()
                .filter(item -> item.type() == type && item.version() == version)
                .findFirst()
                .orElseThrow(() -> new DomainException("Artifact not found"));

        var request = new DocumentRenderRequest(
                offerId,
                artifact.content(),
                artifactTitle(type, offer.name()),
                offer.language(),
                offer.proposalTemplateId(),
                Map.of(
                        "artifactType", type.name(),
                        "artifactVersion", version,
                        "sourceArtifactId", artifact.id().toString(),
                        "offerId", offerId.toString()));
        var rendered = documents.renderMarkdownPdf(request);
        return new RenderedDocument(
                rendered.content(),
                rendered.mediaType(),
                artifactFileName(type, version),
                rendered.templateId(),
                rendered.rendererVersion());
    }

    private static String artifactTitle(ArtifactType type, String offerName) {
        return switch (type) {
            case OPPORTUNITY_BRIEF -> "Opportunity brief · " + offerName;
            case QUESTIONS -> "Questions · " + offerName;
            case TECHNOLOGY -> "Technology analysis · " + offerName;
            case STRATEGY -> "Response strategy · " + offerName;
            case SOLUTION -> "Solution · " + offerName;
            case SOLUTION_PLAN -> "Solution plan · " + offerName;
            case PROPOSAL -> "Proposal · " + offerName;
            case SLIDES_PLAN -> "Slides plan · " + offerName;
            default -> type.name();
        };
    }

    private static String artifactFileName(ArtifactType type, int version) {
        var base = switch (type) {
            case OPPORTUNITY_BRIEF -> "opportunity-brief";
            case QUESTIONS -> "questions";
            case TECHNOLOGY -> "technology";
            case STRATEGY -> "strategy";
            case SOLUTION -> "solution";
            case SOLUTION_PLAN -> "solution-plan";
            case PROPOSAL -> "proposal";
            case SLIDES_PLAN -> "slides-plan";
            default -> type.name().toLowerCase().replace('_', '-');
        };
        return version > 1 ? base + "-v" + version + ".pdf" : base + ".pdf";
    }
}
