package io.github.jaruizes.proposal.infrastructure.client.platform;

import io.github.jaruizes.proposal.domain.ports.CognitivePort;
import io.github.jaruizes.proposal.domain.ports.KnowledgePort;
import io.github.jaruizes.proposal.domain.ports.MemoryPort;
import io.github.jaruizes.proposal.domain.ports.OntologyPort;
import org.springframework.stereotype.Component;

import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;

@Component
public class PlatformPlaceholderAdapters implements KnowledgePort, OntologyPort, MemoryPort, CognitivePort {
    private final Map<String, String> memory = new ConcurrentHashMap<>();

    @Override
    public List<String> search(String scope, String query, int limit) {
        return List.of();
    }

    @Override
    public Map<String, Object> query(String expression) {
        return Map.of();
    }

    @Override
    public void remember(UUID executionId, String key, String value) {
        memory.put(executionId + ":" + key, value);
    }

    @Override
    public Optional<String> recall(UUID executionId, String key) {
        return Optional.ofNullable(memory.get(executionId + ":" + key));
    }

    @Override
    public String reflect(String context, String candidate) {
        return candidate;
    }

    @Override
    public String critique(String context, String candidate) {
        return candidate;
    }
}
