package io.github.jaruizes.proposal.infrastructure.client.source;

import io.github.jaruizes.proposal.domain.ports.DocumentTextExtractorPort;
import org.apache.tika.Tika;
import org.springframework.stereotype.Component;

import java.nio.file.Path;

@Component
public class TikaDocumentTextExtractorAdapter implements DocumentTextExtractorPort {
    private final Tika tika = new Tika();

    @Override
    public String extract(Path path) {
        try {
            var text = tika.parseToString(path);
            return text == null ? "" : text;
        } catch (Exception e) {
            return "[Text extraction warning: " + e.getMessage() + "]";
        }
    }
}
