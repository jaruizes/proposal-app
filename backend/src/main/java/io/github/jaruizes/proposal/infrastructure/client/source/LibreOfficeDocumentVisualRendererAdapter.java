package io.github.jaruizes.proposal.infrastructure.client.source;

import io.github.jaruizes.proposal.domain.ports.DocumentVisualRendererPort;
import org.springframework.stereotype.Component;

import java.nio.file.*;
import java.time.Duration;
import java.util.Optional;
import java.util.concurrent.TimeUnit;

@Component
public class LibreOfficeDocumentVisualRendererAdapter implements DocumentVisualRendererPort {
    @Override
    public Optional<Path> renderPdf(Path source, Path outputDirectory) {
        try {
            Files.createDirectories(outputDirectory);
            var process = new ProcessBuilder("soffice", "--headless", "--convert-to", "pdf", "--outdir",
                    outputDirectory.toString(), source.toString())
                    .redirectErrorStream(true)
                    .start();
            if (!process.waitFor(Duration.ofSeconds(90).toSeconds(), TimeUnit.SECONDS)) {
                process.destroyForcibly();
                return Optional.empty();
            }
            var name=source.getFileName().toString();
            var dot=name.lastIndexOf('.');
            var base=dot>0?name.substring(0,dot):name;
            var pdf=outputDirectory.resolve(base+".pdf");
            return Files.exists(pdf)?Optional.of(pdf):Optional.empty();
        } catch (Exception e) {
            return Optional.empty();
        }
    }
}
