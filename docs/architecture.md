# Architecture

## Intent

`proposal-app` is an extensible agent platform. Proposal Copilot is the first application, not the platform boundary.

```text
Angular
  ↓ REST / SSE
Spring Boot Agent Platform
  ├─ Proposal workflow + human gates
  ├─ Agent Registry
  ├─ Agent Runtime
  ├─ ExecutionGraph (DAG / fork-join)
  ├─ Model Provider port → Anthropic adapter
  ├─ Tool Gateway port → future MCP adapter
  ├─ Knowledge port → future RAG/pgvector
  ├─ Memory port
  ├─ Ontology port → future graph implementation
  ├─ Cognitive port → future planning/reflection/critique services
  └─ Artifact/state persistence → PostgreSQL
```

## Hexagonal rule

All business-capable Spring backend code follows:

```text
infrastructure → business → domain
```

`domain` contains framework-free models, exceptions and ports. `business` implements orchestration/use cases and depends only on domain. `infrastructure` owns REST, JPA/PostgreSQL, Anthropic HTTP, Spring configuration and future MCP/Google adapters.

## Agent orchestration

`AgentTask` is the unit of cognitive work. `ExecutionGraph` models dependencies between tasks. Ready nodes in the same graph wave are executed in parallel; dependent nodes receive accumulated upstream results. This provides deterministic DAG/fork-join orchestration without requiring a paid external orchestration platform.

Proposal phase 3 intentionally remains sequential for its base roles because that behavior was validated in Proposal Copilot:

```text
Solution Architect → Delivery Manager → Business Analyst coherence
```

Optional specialists can later be expressed as parallel `ExecutionGraph` nodes between architect analysis and final integration.

## Future cognitive/knowledge evolution

The platform already defines ports for tools/MCP, knowledge, memory, ontology and cognitive services. Initial adapters are placeholders so these capabilities can be added without reversing dependency direction or coupling Proposal Copilot to a specific runtime/provider.

Recommended evolution:

1. Google Workspace/MCP source adapter and Google Slides adapter.
2. Persisted source manifest and multimodal source ingestion.
3. pgvector semantic knowledge/reusable proposal memory.
4. ontology/knowledge graph adapter (for example Neo4j) behind `OntologyPort`.
5. cognitive services for context selection, contradiction detection, reflection and critique.
6. remote/A2A agent runtime if external agents are introduced.
