package io.github.jaruizes.proposal.business;

import io.github.jaruizes.proposal.domain.exceptions.DomainException;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class OfferWorkflowServiceAnalysisMarkdownTest {
    @Test
    void acceptsRawMarkdownAndOptionalNone() {
        assertThat(OfferWorkflowService.AnalysisMarkdown.required("  # Opportunity\n\nDetails  ", "brief.md"))
                .isEqualTo("# Opportunity\n\nDetails");
        assertThat(OfferWorkflowService.AnalysisMarkdown.optional("NONE", "questions.md")).isNull();
    }

    @Test
    void rejectsJsonAndIncompleteOutputInsteadOfPublishingIt() {
        assertThatThrownBy(() -> OfferWorkflowService.AnalysisMarkdown.required(
                "{\"opportunityBrief\":\"# Opportunity\\nDetails", "brief.md"))
                .isInstanceOf(DomainException.class);
        assertThatThrownBy(() -> OfferWorkflowService.AnalysisMarkdown.required("# Opportunity", "brief.md"))
                .isInstanceOf(DomainException.class);
    }
}
