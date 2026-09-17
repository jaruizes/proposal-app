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
    private final DocumentVisualRendererPort renderer;
    private final ArtifactRepositoryPort artifacts;
    private final ObjectMapper json = new ObjectMapper();

    public SourceIngestionService(ToolGatewayPort tools, DocumentTextExtractorPort extractor,
                                  DocumentVisualRendererPort renderer, ArtifactRepositoryPort artifacts) {
        this.tools = tools;
        this.extractor = extractor;
        this.renderer = renderer;
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
        try {
            var files = listFilesRecursively(folderId);
            files.sort(Comparator.comparing((DriveSource f) -> f.path()).thenComparing(DriveSource::id));

            var entries = new ArrayList<Map<String,Object>>();
            var context = new StringBuilder("# Customer source corpus\n\nOriginal/native customer sources are authoritative. Extracted text and rendered representations are auxiliary.\n");
            var warnings = new ArrayList<String>();
            var attachments = new ArrayList<LlmRequest.Attachment>();
            int i = 1;
            for (var source : files) {
                var file = source.node();
                var code = "DOC-%03d".formatted(i++);
                var fileId = source.id();
                var name = file.path("name").asText();
                var mime = file.path("mimeType").asText();
                var entry = new LinkedHashMap<String,Object>();
                entry.put("id", code);
                entry.put("driveFileId", fileId);
                entry.put("name", name);
                entry.put("relativePath", source.path());
                entry.put("mimeType", mime);
                entry.put("sourceAuthority", "original_native");
                entry.put("representationKind", representationKind(mime));
                entry.put("modifiedTime", file.path("modifiedTime").asText(null));
                entry.put("webViewLink", file.path("webViewLink").asText(null));
                entry.put("status", "ready");
                String extracted;
                String visualPath = null;
                try {
                    if (DOC_MIME.equals(mime)) {
                        extracted = text(tools.execute("docs_get_document", Map.of("documentId", fileId)));
                        visualPath = exportGoogleNative(offer.id(), code, fileId, name, "application/pdf");
                    } else if (SLIDES_MIME.equals(mime)) {
                        extracted = text(tools.execute("slides_get_presentation", Map.of("presentationId", fileId)));
                        visualPath = exportGoogleNative(offer.id(), code, fileId, name, "application/pdf");
                    } else if (SHEETS_MIME.equals(mime)) {
                        extracted = text(tools.execute("sheets_get_spreadsheet", Map.of("spreadsheetId", fileId)));
                        var xlsx = exportGoogleNative(offer.id(), code, fileId, name, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet");
                        if (xlsx != null) extracted += "\n\n# Extracted workbook text\n" + extractor.extract(resolve(xlsx));
                        visualPath = exportGoogleNative(offer.id(), code + "-visual", fileId, name, "application/pdf");
                    } else {
                        var outputPath = "workspace/%s/working/sources/%s-%s".formatted(offer.id(), code, safeName(name));
                        var download = tools.execute("drive_download_file", Map.of("fileId", fileId, "outputPath", outputPath, "overwrite", true));
                        var downloaded = extractOutputPath(text(download));
                        if (downloaded == null) downloaded = outputPath;
                        entry.put("localPath", downloaded);
                        var local=resolve(downloaded);
                        extracted = extractor.extract(local);
                        if ("application/pdf".equals(mime)) {
                            visualPath = downloaded;
                        } else if (isOffice(name,mime)) {
                            var renderedDir=Path.of("/app/workspace",offer.id().toString(),"working","rendered");
                            var rendered=renderer.renderPdf(local,renderedDir);
                            if(rendered.isPresent()) visualPath=Path.of("/app").relativize(rendered.get()).toString();
                            else warnings.add(code+" "+name+": LibreOffice PDF rendering unavailable/failed");
                        }
                    }
                } catch (Exception ex) {
                    extracted = "[Unable to prepare representation: " + ex.getMessage() + "]";
                    warnings.add(code + " " + name + ": " + ex.getMessage());
                    entry.put("status", "warning");
                }
                if (visualPath != null) {
                    entry.put("localVisualPath", visualPath);
                    attachment(resolve(visualPath), name, attachments, warnings);
                }
                entries.add(entry);
                context.append("\n\n## ").append(code).append(" — ").append(source.path())
                        .append("\nMIME: ").append(mime).append("\nDrive ID: ").append(fileId)
                        .append("\nAuthority: original/native source\n\n").append(limit(extracted, 120_000));
            }
            var manifestMap = new LinkedHashMap<String,Object>();
            manifestMap.put("sourceType", "google_drive");
            manifestMap.put("folderId", folderId);
            manifestMap.put("generatedAt", Instant.now().toString());
            manifestMap.put("authorityPolicy", "Original/native customer sources are authoritative; extracted/rendered representations are auxiliary.");
            manifestMap.put("sources", entries);
            manifestMap.put("warnings", warnings);
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

    private List<DriveSource> listFilesRecursively(String rootFolderId) throws Exception {
        var result = new ArrayList<DriveSource>();
        var queue = new ArrayDeque<FolderRef>();
        queue.add(new FolderRef(rootFolderId, ""));
        var visited = new HashSet<String>();

        while (!queue.isEmpty()) {
            var folder = queue.removeFirst();
            if (!visited.add(folder.id())) continue;
            var listing = text(tools.execute("drive_list_folder", Map.of("folderId", folder.id(), "pageSize", 1000)));
            var array = json.readTree(listing);
            if (!array.isArray()) throw new IllegalStateException("drive_list_folder returned a non-array response for folder " + folder.id());
            for (var file : array) {
                var id = file.path("id").asText();
                var name = file.path("name").asText();
                var mime = file.path("mimeType").asText();
                var path = folder.path().isBlank() ? name : folder.path() + "/" + name;
                if (FOLDER_MIME.equals(mime)) queue.addLast(new FolderRef(id, path));
                else result.add(new DriveSource(id, path, file));
            }
        }
        return result;
    }

    private static String representationKind(String mime) {
        if (DOC_MIME.equals(mime) || SLIDES_MIME.equals(mime) || SHEETS_MIME.equals(mime)) return "google_native";
        if ("application/pdf".equals(mime)) return "binary_pdf";
        return "binary";
    }

    private String exportGoogleNative(UUID offerId, String code, String fileId, String name, String mime) {
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
                if (!path.isBlank() && path.endsWith(".pdf")) attachment(resolve(path), source.path("name").asText("source.pdf"), result, new ArrayList<>());
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
    private static Path resolve(String relative){return Path.of("/app").resolve(relative).normalize();}
    private static boolean isOffice(String name,String mime){var n=name.toLowerCase(Locale.ROOT);return n.endsWith(".docx")||n.endsWith(".pptx")||n.endsWith(".xlsx")||mime.contains("officedocument");}
    private static String text(Map<String,Object> result){return Objects.toString(result.get("text"),"");}
    private String extractOutputPath(String text){try{return json.readTree(text).path("outputPath").asText(null);}catch(Exception e){return null;}}
    private static String safeName(String name){return name.replaceAll("[^a-zA-Z0-9._-]+","_");}
    private static String limit(String text,int max){return text.length()<=max?text:text.substring(0,max)+"\n[representation truncated]";}
    private static String extractDriveId(String value){if(value==null)return "";var v=value.trim();var marker="/folders/";var idx=v.indexOf(marker);if(idx>=0){var rest=v.substring(idx+marker.length());var q=rest.indexOf('?');return q>=0?rest.substring(0,q):rest;}return v;}

    private record FolderRef(String id, String path) {}
    private record DriveSource(String id, String path, JsonNode node) {}
}
