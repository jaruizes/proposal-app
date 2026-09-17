package io.github.jaruizes.proposal.domain.ports;

import java.nio.file.Path;
import java.util.Optional;

public interface DocumentVisualRendererPort {
    Optional<Path> renderPdf(Path source, Path outputDirectory);
}
