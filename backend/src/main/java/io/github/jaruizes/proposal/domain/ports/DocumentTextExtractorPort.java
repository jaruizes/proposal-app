package io.github.jaruizes.proposal.domain.ports;

import java.nio.file.Path;

public interface DocumentTextExtractorPort {
    String extract(Path path);
}
