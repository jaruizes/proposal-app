package io.github.jaruizes.proposal.business;

import com.fasterxml.jackson.databind.ObjectMapper;
import io.github.jaruizes.proposal.domain.model.*;
import io.github.jaruizes.proposal.domain.ports.ArtifactRepositoryPort;
import org.springframework.stereotype.Service;

import java.time.Instant;
import java.util.*;

/**
 * Application-facing source preparation service.
 *
 * Spring never calls Google Workspace MCP directly. Source discovery/read/download
 * is one standard AgentExecution owned by Agent Platform's source-ingestion graph.
 */
@Service
public class SourceIngestionService {
    private final AgentRuntimeService agents;
    private final ArtifactRepositoryPort artifacts;
    private final ObjectMapper json = new ObjectMapper();

    public SourceIngestionService(AgentRuntimeService agents, ArtifactRepositoryPort artifacts) {
        this.agents = agents;
        this.artifacts = artifacts;
    }

    public SourceBundle loadOrIngest(Offer offer) {
        var manifest = artifacts.findLatest(offer.id(), ArtifactType.SOURCE_MANIFEST);
        var context = artifacts.findLatest(offer.id(), ArtifactType.SOURCE_CONTEXT);
        var report = artifacts.findLatest(offer.id(), ArtifactType.SOURCE_INGESTION_REPORT);
        if (manifest.isPresent() && context.isPresent()) {
            return new SourceBundle(
                    manifest.get().content(),
                    context.get().content(),
                    List.of(),
                    report.map(Artifact::content).orElse("Previously ingested source corpus."));
        }

        var result = agents.execute(
                AgentTask.of(
                        offer.id(),
                        PhaseType.ANALYSIS,
                        "business-analyst",
                        "ingest-sources",
                        "Preparar fuentes de entrada",
                        """
                        Execute ingest-sources exactly.
                        Discover and prepare the Google Drive source corpus using Agent Platform tools.
                        Return ONLY the canonical JSON bundle defined by the source-ingestion graph.
                        Do not perform semantic opportunity analysis.
                        """)
                        .withOutputFormat("json")
                        .withCheckpoint("sources.ingestion"),
                offer.models().getOrDefault("analysis", "claude-sonnet-4-6"),
                "Offer name: %s\nOrganization: %s\nGoogle Drive input folder: %s\n"
                        .formatted(offer.name(), offer.customer(), offer.inputDriveFolder()));

        try {
            var root = json.readTree(result.content());
            var manifestNode = root.path("manifest");
            var textualContext = root.path("textualContext").asText("");
            var ingestionReport = root.path("ingestionReport").asText("");
            if (!manifestNode.isObject() || textualContext.isBlank())
                throw new IllegalStateException("Agent Platform returned an incomplete source bundle");

            var manifestJson = json.writerWithDefaultPrettyPrinter().writeValueAsString(manifestNode);
            save(offer.id(), ArtifactType.SOURCE_MANIFEST, manifestJson);
            save(offer.id(), ArtifactType.SOURCE_CONTEXT, textualContext);
            save(offer.id(), ArtifactType.SOURCE_INGESTION_REPORT, ingestionReport);
            return new SourceBundle(manifestJson, textualContext, List.of(), ingestionReport);
        } catch (Exception e) {
            throw new IllegalStateException("Invalid source-ingestion result from Agent Platform", e);
        }
    }

    /**
     * Narrows an already ingested source corpus to originals selected by solution triage.
     * No Google/MCP access occurs here; this is deterministic application logic.
     */
    public SourceBundle selectForSolution(SourceBundle bundle, String triageJson) {
        try {
            var root = json.readTree(triageJson);
            var selected = new LinkedHashSet<String>();
            root.path("sourceReview").forEach(node -> {
                var disposition = node.path("disposition").asText("");
                var id = node.path("id").asText("");
                if (!id.isBlank() && ("REVIEW_IN_DEPTH".equals(disposition) || "TARGETED_REVIEW".equals(disposition))) {
                    selected.add(id);
                }
            });
            if (selected.isEmpty()) {
                return new SourceBundle(
                        bundle.manifest(),
                        "# Selected original customer evidence\n\nNo original sources were selected by triage.",
                        List.of(),
                        bundle.ingestionReport());
            }

            var manifestRoot = json.readTree(bundle.manifest());
            var filtered = (com.fasterxml.jackson.databind.node.ObjectNode) manifestRoot.deepCopy();
            var sourcesNode = filtered.withArray("sources");
            sourcesNode.removeAll();
            manifestRoot.path("sources").forEach(node -> {
                if (selected.contains(node.path("id").asText())) sourcesNode.add(node.deepCopy());
            });
            filtered.put("selectedBySolutionTriage", true);
            filtered.put("selectedSourceCount", sourcesNode.size());
            var filteredManifest = json.writerWithDefaultPrettyPrinter().writeValueAsString(filtered);

            var context = new StringBuilder("# Selected original customer evidence\n\n")
                    .append("Only sources selected by solution triage are included below. Original/native customer sources remain authoritative.\n");
            var pattern = java.util.regex.Pattern.compile("(?m)^## (DOC-\\d{3}) — ");
            var matcher = pattern.matcher(bundle.textualContext());
            var starts = new ArrayList<Integer>();
            var ids = new ArrayList<String>();
            while (matcher.find()) {
                starts.add(matcher.start());
                ids.add(matcher.group(1));
            }
            for (int i = 0; i < starts.size(); i++) {
                if (!selected.contains(ids.get(i))) continue;
                var end = i + 1 < starts.size() ? starts.get(i + 1) : bundle.textualContext().length();
                context.append("\n\n").append(bundle.textualContext(), starts.get(i), end);
            }
            return new SourceBundle(filteredManifest, context.toString(), List.of(), bundle.ingestionReport());
        } catch (Exception e) {
            return bundle;
        }
    }

    private void save(UUID offerId, ArtifactType type, String content) {
        var latest = artifacts.findLatest(offerId, type);
        if (latest.isPresent() && Objects.equals(latest.get().content(), content)) return;
        artifacts.save(new Artifact(
                UUID.randomUUID(),
                offerId,
                PhaseType.ANALYSIS,
                type,
                artifacts.nextVersion(offerId, type),
                content,
                Instant.now()));
    }
}
