package io.github.jaruizes.proposal.infrastructure.api.rest;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import io.github.jaruizes.proposal.infrastructure.client.platform.AgentPlatformProperties;
import org.springframework.core.io.ByteArrayResource;
import org.springframework.http.MediaType;
import org.springframework.http.client.MultipartBodyBuilder;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;
import org.springframework.web.reactive.function.BodyInserters;
import org.springframework.web.reactive.function.client.WebClient;
import org.springframework.web.reactive.function.client.ExchangeStrategies;

import java.util.Map;

@RestController
@RequestMapping("/api/knowledge")
@CrossOrigin(origins = "*")
public class KnowledgeController {
    private final WebClient client;
    private final ObjectMapper mapper;

    public KnowledgeController(AgentPlatformProperties properties, WebClient.Builder builder, ObjectMapper mapper) {
        this.mapper = mapper;
        var strategies = ExchangeStrategies.builder()
                .codecs(configurer -> configurer.defaultCodecs().maxInMemorySize(8 * 1024 * 1024))
                .build();
        var configured = builder.baseUrl(properties.baseUrl()).exchangeStrategies(strategies);
        if (properties.apiKey() != null && !properties.apiKey().isBlank()) {
            configured.defaultHeader("X-API-Key", properties.apiKey());
        }
        this.client = configured.build();
    }

    @GetMapping("/bases")
    public JsonNode bases() { return get("/v1/knowledge-bases"); }

    @PostMapping("/bases/bootstrap")
    public JsonNode bootstrap() {
        return client.post().uri("/v1/knowledge-bases/bootstrap").retrieve().bodyToMono(JsonNode.class).block();
    }

    @GetMapping("/bases/{key}/documents")
    public JsonNode documents(@PathVariable String key) { return get("/v1/knowledge-bases/" + key + "/documents"); }

    @GetMapping("/documents/{id}")
    public JsonNode document(@PathVariable String id) { return get("/v1/knowledge-documents/" + id); }

    @GetMapping("/documents/{id}/versions")
    public JsonNode versions(@PathVariable String id) { return get("/v1/knowledge-documents/" + id + "/versions"); }

    @PostMapping("/documents/{id}/archive")
    public JsonNode archive(@PathVariable String id) { return client.post().uri("/v1/knowledge-documents/{id}/archive",id).retrieve().bodyToMono(JsonNode.class).block(); }

    @PostMapping("/documents/{id}/restore")
    public JsonNode restore(@PathVariable String id) { return client.post().uri("/v1/knowledge-documents/{id}/restore",id).retrieve().bodyToMono(JsonNode.class).block(); }

    @DeleteMapping("/documents/{id}")
    public void deleteDocument(@PathVariable String id) { client.delete().uri("/v1/knowledge-documents/{id}",id).retrieve().toBodilessEntity().block(); }

    @PostMapping(value="/documents/{id}/versions", consumes=MediaType.MULTIPART_FORM_DATA_VALUE)
    public JsonNode uploadVersion(@PathVariable String id,@RequestPart("file") MultipartFile file,
            @RequestParam(defaultValue="fixed") String chunkingStrategy,
            @RequestParam(defaultValue="standard") String metadataEnrichment) throws Exception {
        var multipart=new MultipartBodyBuilder();
        var resource=new ByteArrayResource(file.getBytes()){ @Override public String getFilename(){return file.getOriginalFilename()==null?"document":file.getOriginalFilename();}};
        multipart.part("file",resource).contentType(file.getContentType()==null?MediaType.APPLICATION_OCTET_STREAM:MediaType.parseMediaType(file.getContentType()));
        multipart.part("chunking_strategy",chunkingStrategy); multipart.part("metadata_enrichment",metadataEnrichment);
        return client.post().uri("/v1/knowledge-documents/{id}/versions",id).contentType(MediaType.MULTIPART_FORM_DATA)
                .body(BodyInserters.fromMultipartData(multipart.build())).retrieve().bodyToMono(JsonNode.class).block();
    }

    @GetMapping("/documents/{id}/chunks")
    public JsonNode chunks(
            @PathVariable String id,
            @RequestParam(defaultValue = "0") int offset,
            @RequestParam(defaultValue = "100") int limit) {
        var safeLimit = Math.max(1, Math.min(limit, 500));
        var safeOffset = Math.max(0, offset);
        return get("/v1/knowledge-documents/" + id + "/chunks?offset=" + safeOffset + "&limit=" + safeLimit);
    }

    @PostMapping(value = "/bases/{key}/files", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public JsonNode upload(
            @PathVariable String key,
            @RequestPart("file") MultipartFile file,
            @RequestParam(defaultValue = "fixed") String chunkingStrategy,
            @RequestParam(defaultValue = "standard") String metadataEnrichment,
            @RequestParam(defaultValue = "1200") int chunkSize,
            @RequestParam(defaultValue = "200") int overlap,
            @RequestParam(defaultValue = "6000") int parentSize,
            @RequestParam(defaultValue = "1200") int childSize,
            @RequestParam(defaultValue = "200") int childOverlap,
            @RequestParam(defaultValue = "8") int maxKeywords,
            @RequestParam(required = false) String customer,
            @RequestParam(required = false) String sector,
            @RequestParam(required = false) Integer year,
            @RequestParam(required = false) String proposalType,
            @RequestParam(required = false) String tags
    ) throws Exception {
        var metadata = new java.util.LinkedHashMap<String, Object>();
        putIfPresent(metadata, "customer", customer);
        putIfPresent(metadata, "sector", sector);
        if (year != null) metadata.put("year", year);
        putIfPresent(metadata, "proposal_type", proposalType);
        if (tags != null && !tags.isBlank()) {
            metadata.put("tags", java.util.Arrays.stream(tags.split(",")).map(String::trim).filter(s -> !s.isBlank()).toList());
        }

        var multipart = new MultipartBodyBuilder();
        var resource = new ByteArrayResource(file.getBytes()) {
            @Override public String getFilename() {
                return file.getOriginalFilename() == null ? "document" : file.getOriginalFilename();
            }
        };
        multipart.part("file", resource).contentType(
                file.getContentType() == null ? MediaType.APPLICATION_OCTET_STREAM : MediaType.parseMediaType(file.getContentType()));
        multipart.part("metadata", mapper.writeValueAsString(metadata));
        multipart.part("ingest", "true");
        multipart.part("embed", "true");
        multipart.part("chunking_strategy", chunkingStrategy);
        multipart.part("metadata_enrichment", metadataEnrichment);
        multipart.part("chunk_size", Integer.toString(chunkSize));
        multipart.part("overlap", Integer.toString(overlap));
        multipart.part("parent_size", Integer.toString(parentSize));
        multipart.part("child_size", Integer.toString(childSize));
        multipart.part("child_overlap", Integer.toString(childOverlap));
        multipart.part("max_keywords", Integer.toString(maxKeywords));

        return client.post()
                .uri("/v1/knowledge-bases/{key}/files", key)
                .contentType(MediaType.MULTIPART_FORM_DATA)
                .body(BodyInserters.fromMultipartData(multipart.build()))
                .retrieve().bodyToMono(JsonNode.class).block();
    }

    @PostMapping("/retrieve")
    public JsonNode retrieve(@RequestBody JsonNode payload) {
        return client.post().uri("/v1/knowledge/retrieve").contentType(MediaType.APPLICATION_JSON)
                .bodyValue(payload).retrieve().bodyToMono(JsonNode.class).block();
    }

    private JsonNode get(String uri) {
        return client.get().uri(uri).retrieve().bodyToMono(JsonNode.class).block();
    }

    private static void putIfPresent(Map<String, Object> target, String key, String value) {
        if (value != null && !value.isBlank()) target.put(key, value.trim());
    }
}
