package io.github.jaruizes.proposal.domain.ports;

import io.github.jaruizes.proposal.domain.model.DocumentRenderRequest;
import io.github.jaruizes.proposal.domain.model.RenderedDocument;

public interface DocumentPort {
    RenderedDocument renderProposalDocx(DocumentRenderRequest request);
    RenderedDocument renderMarkdownPdf(DocumentRenderRequest request);
}
