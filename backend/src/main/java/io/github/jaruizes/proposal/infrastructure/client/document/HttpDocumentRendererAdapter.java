package io.github.jaruizes.proposal.infrastructure.client.document;

import io.github.jaruizes.proposal.domain.model.DocumentRenderRequest;
import io.github.jaruizes.proposal.domain.model.RenderedDocument;
import io.github.jaruizes.proposal.domain.ports.DocumentPort;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.reactive.function.client.WebClient;

import java.util.LinkedHashMap;

@Component
public class HttpDocumentRendererAdapter implements DocumentPort {
    private final WebClient client;

    public HttpDocumentRendererAdapter(WebClient.Builder builder,
                                       @Value("${proposal-document.renderer-url:http://localhost:8090}") String baseUrl) {
        this.client = builder.baseUrl(baseUrl).build();
    }

    @Override
    public RenderedDocument renderProposalDocx(DocumentRenderRequest request) {
        var body = new LinkedHashMap<String,Object>();
        body.put("markdown", request.markdown());
        body.put("title", request.title());
        body.put("language", request.language());
        body.put("template_id", request.templateId());
        body.put("metadata", request.metadata());

        var response = client.post()
                .uri("/v1/render/docx")
                .contentType(MediaType.APPLICATION_JSON)
                .accept(MediaType.parseMediaType("application/vnd.openxmlformats-officedocument.wordprocessingml.document"))
                .bodyValue(body)
                .retrieve()
                .toEntity(byte[].class)
                .block();

        if (response == null || response.getBody() == null || response.getBody().length == 0) {
            throw new IllegalStateException("Document renderer returned an empty DOCX");
        }
        var headers = response.getHeaders();
        var rendererVersion = headers.getFirst("X-Renderer-Version");
        var templateId = headers.getFirst("X-Template-Id");
        var fileName = headers.getContentDisposition().getFilename();
        if (fileName == null || fileName.isBlank()) fileName = "proposal.docx";
        return new RenderedDocument(
                response.getBody(),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                fileName,
                templateId == null ? request.templateId() : templateId,
                rendererVersion == null ? "unknown" : rendererVersion);
    }

    @Override
    public RenderedDocument renderMarkdownPdf(DocumentRenderRequest request) {
        var body = new LinkedHashMap<String,Object>();
        body.put("markdown", request.markdown());
        body.put("title", request.title());
        body.put("language", request.language());
        body.put("template_id", request.templateId());
        body.put("metadata", request.metadata());

        var response = client.post()
                .uri("/v1/render/pdf")
                .contentType(MediaType.APPLICATION_JSON)
                .accept(MediaType.APPLICATION_PDF)
                .bodyValue(body)
                .retrieve()
                .toEntity(byte[].class)
                .block();

        if (response == null || response.getBody() == null || response.getBody().length == 0) {
            throw new IllegalStateException("Document renderer returned an empty PDF");
        }
        var headers = response.getHeaders();
        var rendererVersion = headers.getFirst("X-Renderer-Version");
        var templateId = headers.getFirst("X-Template-Id");
        var fileName = headers.getContentDisposition().getFilename();
        if (fileName == null || fileName.isBlank()) fileName = "artifact.pdf";
        return new RenderedDocument(
                response.getBody(),
                MediaType.APPLICATION_PDF_VALUE,
                fileName,
                templateId == null ? request.templateId() : templateId,
                rendererVersion == null ? "unknown" : rendererVersion);
    }
}
