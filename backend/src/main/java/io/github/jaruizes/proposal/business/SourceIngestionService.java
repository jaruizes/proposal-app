package io.github.jaruizes.proposal.business;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import io.github.jaruizes.proposal.domain.model.*;
import io.github.jaruizes.proposal.domain.ports.*;
import org.springframework.stereotype.Service;

import java.nio.file.*;
import java.time.Instant;
import java.util.*;
import java.util.Base64;

/** Implements the validated ingest-sources contract using the Google Workspace MCP server. */
@Service
public class SourceIngestionService {
    private static final String FOLDER_MIME = "application/vnd.google-apps.folder";
    private static final String DOC_MIME = "application/vnd.google-apps.document";
    private static final String SLIDES_MIME = "application/vnd.google-apps.presentation";
    private static final String SHEETS_MIME = "application/vnd.google-apps.spreadsheet";
    private static final long MAX_ATTACHMENT_BYTES = 20L * 1024 * 1024;

    private final ToolGatewayPort tools;
    private final DocumentTextExtractorPort extractor;
    private final ArtifactRepositoryPort artifacts;
    private final ObjectMapper json = new ObjectMapper();

    public SourceIngestionService(ToolGatewayPort tools, DocumentTextExtractorPort extractor, ArtifactRepositoryPort artifacts) {
        this.tools = tools;
        this.extractor = extractor;
        this.artifacts = artifacts;
    }

    public SourceBundle loadOrIngest(Offer offer) {
        var manifest = artifacts.findLatest(offer.id(), ArtifactType.SOURCE_MANIFEST);
        var context = artifacts.findLatest(offer.id(), ArtifactType.SOURCE_CONTEXT);
        var report = artifacts.findLatest(offer.id(), ArtifactType.SOURCE_INGESTION_REPORT);
        if (manifest.isPresent() && context.isPresent()) {
            return new SourceBundle(manifest.get().content(), context.get().content(), attachmentsFromManifest(manifest.get().content()),
                    report.map(Artifact::content).orElse("Previously ingested source corpus."));
        }
        return ingest(offer);
    }

    public SourceBundle ingest(Offer offer) {
        var folderId = extractDriveId(offer.inputDriveFolder());
        if (folderId.isBlank()) throw new IllegalArgumentException("Google Drive input folder ID/URL is required");
        var listing = text(tools.execute("drive_list_folder", Map.of("folderId", folderId, "pageSize", 1000)));
        try {
            var array = json.readTree(listing);
            var files = new ArrayList<JsonNode>();
            array.forEach(files::add);
            files.removeIf(f -> FOLDER_MIME.equals(f.path("mimeType").asText()));
            files.sort(Comparator.comparing((JsonNode f) -> f.path("name").asText()).thenComparing(f -> f.path("id").asText()));

            var entries = new ArrayList<Map<String,Object>>();
            var context = new StringBuilder("# Customer source corpus\n\n");
            var warnings = new ArrayList<String>();
            var attachments = new ArrayList<LlmRequest.Attachment>();
            int i = 1;
            for (var file : files) {
                var code = "DOC-%03d".formatted(i++);
                var fileId = file.path("id").asText();
                var name = file.path("name").asText();
                var mime = file.path("mimeType").asText();
                var entry = new LinkedHashMap<String,Object>();
                entry.put("id", code); entry.put("driveFileId", fileId); entry.put("name", name); entry.put("mimeType", mime);
                entry.put("modifiedTime", file.path("modifiedTime").asText(null)); entry.put("webViewLink", file.path("webViewLink").asText(null));
                entry.put("status", "ready");
                String extracted;
                String visualPath = null;
                try {
                    if (DOC_MIME.equals(mime)) {
                        extracted = text(tools.execute("docs_get_document", Map.of("documentId", fileId)));
                        visualPath = exportVisual(offer.id(), code, fileId, name, "application/pdf");
                    } else if (SLIDES_MIME.equals(mime)) {
                        extracted = text(tools.execute("slides_get_presentation", Map.of("presentationId", fileId)));
                        visualPath = exportVisual(offer.id(), code, fileId, name, "application/pdf");
                    } else if (SHEETS_MIME.equals(mime)) {
                        extracted = text(tools.execute("sheets_get_spreadsheet", Map.of("spreadsheetId", fileId)));
                        var xlsx = exportVisual(offer.id(), code, fileId, name, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet");
                        if (xlsx != null) extracted += "\n\n# Extracted workbook text\n" + extractor.extract(Path.of("/app", xlsx));
                        visualPath = exportVisual(offer.id(), code + "-visual", fileId, name, "application/pdf");
                    } else {
                        var safe = safeName(name);
                        var outputPath = "workspace/%s/working/sources/%s-%s".formatted(offer.id(), code, safe);
                        var download = tools.execute("drive_download_file", Map.of("fileId", fileId, "outputPath", outputPath, "overwrite", true));
                        var downloaded = extractOutputPath(text(download));
                        if (downloaded == null) downloaded = outputPath;
                        entry.put("localPath", downloaded);
                        extracted = extractor.extract(Path.of("/app", downloaded));
                        if ("application/pdf".equals(mime)) visualPath = downloaded;
                    }
                } catch (Exception ex) {
                    extracted = "[Unable to prepare representation: " + ex.getMessage() + "]";
                    warnings.add(code + " " + name + ": " + ex.getMessage());
                    entry.put("status", "warning");
                }
                if (visualPath != null) {
                    entry.put("localVisualPath", visualPath);
                    attachment(Path.of("/app", visualPath), name, attachments, warnings);
                }
                entries.add(entry);
                context.append("\n\n## ").append(code).append(" — ").append(name)
                        .append("\nMIME: ").append(mime).append("\nDrive ID: ").append(fileId)
                        .append("\n\n").append(limit(extracted, 120_000));
            }
            var manifestMap = new LinkedHashMap<String,Object>();
            manifestMap.put("sourceType", "google_drive"); manifestMap.put("folderId", folderId); manifestMap.put("generatedAt", Instant.now().toString());
            manifestMap.put("sources", entries); manifestMap.put("warnings", warnings);
            var manifestJson = json.writerWithDefaultPrettyPrinter().writeValueAsString(manifestMap);
            var reportText = "Google Drive ingestion completed: %d documents, %d warnings, %d multimodal PDF attachments. Original/native sources remain authoritative.".formatted(entries.size(), warnings.size(), attachments.size());
            save(offer.id(), ArtifactType.SOURCE_MANIFEST, manifestJson);
            save(offer.id(), ArtifactType.SOURCE_CONTEXT, context.toString());
            save(offer.id(), ArtifactType.SOURCE_INGESTION_REPORT, reportText);
            return new SourceBundle(manifestJson, context.toString(), attachments, reportText);
        } catch (Exception e) {
            throw new IllegalStateException("Source ingestion failed", e);
        }
    }

    private String exportVisual(UUID offerId, String code, String fileId, String name, String mime) {
        var extension = mime.equals("application/pdf") ? ".pdf" : ".xlsx";
        var output = "workspace/%s/working/rendered/%s-%s%s".formatted(offerId, code, safeName(name), extension);
        var result = tools.execute("drive_export_file", Map.of("fileId", fileId, "mimeType", mime, "outputPath", output, "overwrite", true));
        var parsed = extractOutputPath(text(result));
        return parsed == null ? output : parsed;
    }

    private List<LlmRequest.Attachment> attachmentsFromManifest(String manifest) {
        var result = new ArrayList<LlmRequest.Attachment>();
        try {
            json.readTree(manifest).path("sources").forEach(source -> {
                var path = source.path("localVisualPath").asText("");
                if (!path.isBlank() && path.endsWith(".pdf")) attachment(Path.of("/app", path), source.path("name").asText("source.pdf"), result, new ArrayList<>());
            });
        } catch (Exception ignored) {}
        return result;
    }

    private void attachment(Path path, String name, List<LlmRequest.Attachment> target, List<String> warnings) {
        try {
            if (!Files.exists(path) || !path.toString().toLowerCase(Locale.ROOT).endsWith(".pdf")) return;
            var bytes = Files.readAllBytes(path);
            if (bytes.length > MAX_ATTACHMENT_BYTES) { warnings.add(name + ": PDF too large for multimodal attachment"); return; }
            target.add(new LlmRequest.Attachment("application/pdf", Base64.getEncoder().encodeToString(bytes), name));
        } catch (Exception e) { warnings.add(name + ": could not attach PDF: " + e.getMessage()); }
    }

    private void save(UUID offerId, ArtifactType type, String content) {
        artifacts.save(new Artifact(UUID.randomUUID(), offerId, PhaseType.ANALYSIS, type, artifacts.nextVersion(offerId,type), content, Instant.now()));
    }
    private static String text(Map<String,Object> result){return Objects.toString(result.get("text"),"");}
    private String extractOutputPath(String text){try{return json.readTree(text).path("outputPath").asText(null);}catch(Exception e){return null;}}
    private static String safeName(String name){return name.replaceAll("[^a-zA-Z0-9._-]+","_");}
    private static String limit(String text,int max){return text.length()<=max?text:text.substring(0,max)+"\n[representation truncated]";}
    private static String extractDriveId(String value){if(value==null)return "";var v=value.trim();var marker="/folders/";var idx=v.indexOf(marker);if(idx>=0){var rest=v.substring(idx+marker.length());var q=rest.indexOf('?');return q>=0?rest.substring(0,q):rest;}return v;}
}
