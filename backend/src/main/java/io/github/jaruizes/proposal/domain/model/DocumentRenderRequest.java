package io.github.jaruizes.proposal.domain.model;

import java.util.Map;
import java.util.UUID;

public record DocumentRenderRequest(
        UUID offerId,
        String markdown,
        String title,
        String language,
        String templateId,
        Map<String,Object> metadata) {}
