package io.github.jaruizes.proposal.domain.ports;
import java.util.*;
public interface MemoryPort { void remember(UUID executionId, String key, String value); Optional<String> recall(UUID executionId, String key); }
