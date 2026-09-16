package io.github.jaruizes.proposal.domain.model;
import java.util.Set;
public record AgentDefinition(String key, String name, String role, Set<String> capabilities, Set<String> allowedTools, String promptResource) {}
