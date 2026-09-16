package io.github.jaruizes.proposal.business;

import io.github.jaruizes.proposal.domain.exceptions.DomainException;
import io.github.jaruizes.proposal.domain.model.*;
import org.springframework.stereotype.Service;

import java.util.*;

@Service
public class ExecutionGraphService {
    private final AgentRuntimeService runtime;
    public ExecutionGraphService(AgentRuntimeService runtime) { this.runtime = runtime; }

    public Map<String,LlmResult> execute(ExecutionGraph graph, String model, String baseContext) {
        var pending = new LinkedHashMap<String,ExecutionGraph.Node>();
        graph.nodes().forEach(n -> pending.put(n.id(), n));
        var completed = new LinkedHashMap<String,LlmResult>();
        while (!pending.isEmpty()) {
            var ready = pending.values().stream().filter(n -> completed.keySet().containsAll(n.dependsOn())).toList();
            if (ready.isEmpty()) throw new DomainException("Execution graph contains a cycle or missing dependency");
            var context = new StringBuilder(baseContext);
            completed.forEach((id,result) -> context.append("\n\n## Result ").append(id).append("\n").append(result.content()));
            var results = runtime.executeParallel(ready.stream().map(ExecutionGraph.Node::task).toList(), model, context.toString());
            for (int i=0;i<ready.size();i++) { completed.put(ready.get(i).id(), results.get(i)); pending.remove(ready.get(i).id()); }
        }
        return completed;
    }
}
