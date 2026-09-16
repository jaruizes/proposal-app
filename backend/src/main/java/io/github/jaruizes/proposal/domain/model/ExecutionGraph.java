package io.github.jaruizes.proposal.domain.model;

import java.util.List;
import java.util.Set;

public record ExecutionGraph(List<Node> nodes) {
    public record Node(String id, AgentTask task, Set<String> dependsOn) {}
}
