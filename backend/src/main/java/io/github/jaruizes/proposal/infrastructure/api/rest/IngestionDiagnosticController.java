package io.github.jaruizes.proposal.infrastructure.api.rest;

import io.github.jaruizes.proposal.business.SourceIngestionService;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

@RestController
@RequestMapping("/api/diagnostics/ingestion")
public class IngestionDiagnosticController {

    private final SourceIngestionService sourceIngestionService;

    public IngestionDiagnosticController(SourceIngestionService sourceIngestionService) {
        this.sourceIngestionService = sourceIngestionService;
    }

    @GetMapping("/google-drive")
    public ResponseEntity<Map<String, Object>> googleDrive(
            @RequestParam("folderId") String folderId) {
        return ResponseEntity.ok(sourceIngestionService.inspectDriveFolder(folderId));
    }
}
