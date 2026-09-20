package io.github.jaruizes.proposal.infrastructure.client.source;

import io.github.jaruizes.proposal.domain.ports.DocumentVisualRendererPort;
import org.springframework.stereotype.Component;

import java.nio.file.*;
import java.time.Duration;
import java.util.Optional;
import java.util.UUID;
import java.util.concurrent.TimeUnit;

@Component
public class LibreOfficeDocumentVisualRendererAdapter implements DocumentVisualRendererPort {
    @Override
    public Optional<Path> renderPdf(Path source, Path outputDirectory) {
        Path profileDirectory = null;
        try {
            Files.createDirectories(outputDirectory);
            profileDirectory = Files.createTempDirectory("lo-profile-");
            var profileUri = profileDirectory.toUri().toString();
            var process = new ProcessBuilder(
                    "soffice",
                    "-env:UserInstallation=" + profileUri,
                    "--headless",
                    "--nologo",
                    "--nodefault",
                    "--nofirststartwizard",
                    "--convert-to", "pdf",
                    "--outdir", outputDirectory.toString(),
                    source.toString())
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
            return process.exitValue()==0 && Files.exists(pdf)?Optional.of(pdf):Optional.empty();
        } catch (Exception e) {
            return Optional.empty();
        } finally {
            if (profileDirectory != null) {
                try (var walk = Files.walk(profileDirectory)) {
                    walk.sorted(java.util.Comparator.reverseOrder()).forEach(path -> {
                        try { Files.deleteIfExists(path); } catch (Exception ignored) {}
                    });
                } catch (Exception ignored) {}
            }
        }
    }
}
