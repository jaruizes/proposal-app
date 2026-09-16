package io.github.jaruizes.proposal.domain.ports;
import java.util.UUID;
public interface PresentationPort { PresentationResult materialize(UUID offerId, String slidesPlan, String outputFolder, String documentName); record PresentationResult(String externalId, String url, String buildReport) {} }
