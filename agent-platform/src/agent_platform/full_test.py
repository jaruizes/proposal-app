from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
import uuid


EXPECTED_SKILLS = {
    "create-offer",
    "ingest-sources",
    "qualify-opportunity",
    "design-solution",
    "plan-delivery",
    "compose-proposal",
    "design-presentation",
    "generate-presentation",
}

EXPECTED_AGENTS = {
    "business-analyst",
    "solution-architect",
    "delivery-manager",
    "security-specialist",
}

EXPECTED_KNOWLEDGE_BASES = {
    "reference-offers",
    "architecture-references",
    "corporate-roles",
    "corporate-capabilities",
    "accelerators",
    "case-studies",
}


class SmokeFailure(RuntimeError):
    pass


class Client:
    def __init__(self, base_url: str, api_key: str | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    def request(self, method: str, path: str, body=None, expected=(200,)):
        headers = {"Accept": "application/json"}
        payload = None
        if body is not None:
            headers["Content-Type"] = "application/json"
            payload = json.dumps(body).encode()
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        request = urllib.request.Request(self.base_url + path, data=payload, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                raw = response.read()
                status = response.status
                response_headers = dict(response.headers.items())
        except urllib.error.HTTPError as exc:
            raw = exc.read()
            status = exc.code
            response_headers = dict(exc.headers.items())
        if status not in expected:
            raise SmokeFailure(f"{method} {path} returned {status}: {raw.decode(errors='replace')}")
        if not raw:
            return None, response_headers
        try:
            return json.loads(raw), response_headers
        except json.JSONDecodeError:
            return raw.decode(errors="replace"), response_headers

    def get(self, path: str, expected=(200,)):
        return self.request("GET", path, expected=expected)

    def post(self, path: str, body=None, expected=(200,)):
        return self.request("POST", path, body, expected)

    def delete(self, path: str, expected=(204,)):
        return self.request("DELETE", path, expected=expected)


def check(condition: bool, message: str) -> None:
    if not condition:
        raise SmokeFailure(message)


def log(message: str) -> None:
    print(f"[M23] {message}", flush=True)


def assert_empty(client: Client) -> None:
    agents, _ = client.get("/v1/agents")
    skills, _ = client.get("/v1/skills")
    bases, _ = client.get("/v1/knowledge-bases")
    concepts, _ = client.get("/v1/ontology/concepts")
    check(agents == [], f"Expected clean agents table, found {len(agents)}")
    check(skills == [], f"Expected clean skills table, found {len(skills)}")
    check(bases == [], f"Expected clean knowledge bases, found {len(bases)}")
    check(concepts == [], f"Expected clean ontology, found {len(concepts)}")
    log("clean database verified")


def verify_catalog(client: Client) -> None:
    skills, _ = client.get("/v1/skills")
    agents, _ = client.get("/v1/agents")
    skill_keys = {item["key"] for item in skills}
    agent_keys = {item["key"] for item in agents}
    check(skill_keys == EXPECTED_SKILLS, f"Unexpected skills: {sorted(skill_keys)}")
    check(agent_keys == EXPECTED_AGENTS, f"Unexpected agents: {sorted(agent_keys)}")
    for agent in agents:
        missing = set(agent.get("skills", [])) - skill_keys
        check(not missing, f"Agent {agent['key']} references missing skills: {sorted(missing)}")
    log("4 agents + 8 skills verified, including cross references")


def bootstrap_knowledge(client: Client) -> None:
    client.post("/v1/knowledge-bases/bootstrap", {}, expected=(200,))
    bases, _ = client.get("/v1/knowledge-bases")
    keys = {item["key"] for item in bases}
    check(keys == EXPECTED_KNOWLEDGE_BASES, f"Unexpected knowledge bases: {sorted(keys)}")
    log("6 default knowledge bases verified")


def exercise_platform(client: Client, real_model: bool) -> None:
    ready, headers = client.get("/health/ready")
    check(ready["status"] == "ready", f"Platform not ready: {ready}")
    check(headers.get("X-Request-ID") or headers.get("x-request-id"), "Missing X-Request-ID")
    log("liveness/readiness + hardening headers verified")

    overview, _ = client.get("/v1/admin/overview")
    check(overview["counts"]["agents"] == 4, "Admin overview agent count mismatch")
    check(overview["counts"]["skills"] == 8, "Admin overview skill count mismatch")
    log("admin API verified")

    suffix = uuid.uuid4().hex[:8]
    concept_container = f"m23.container-{suffix}"
    concept_openshift = f"m23.openshift-{suffix}"
    client.post("/v1/ontology/concepts", {
        "key": concept_container,
        "name": f"M23 Container Platform {suffix}",
        "type": "platform",
        "description": "Milestone 23 clean-room smoke concept",
        "aliases": [f"M23CP{suffix}"],
        "metadata": {},
        "enabled": True,
    }, expected=(201,))
    client.post("/v1/ontology/concepts", {
        "key": concept_openshift,
        "name": f"M23 OpenShift {suffix}",
        "type": "technology",
        "description": "Milestone 23 clean-room smoke technology",
        "aliases": [f"M23OCP{suffix}"],
        "metadata": {},
        "enabled": True,
    }, expected=(201,))
    relationship, _ = client.post("/v1/ontology/relationships", {
        "source_key": concept_openshift,
        "relation": "IS_A",
        "target_key": concept_container,
        "metadata": {},
    }, expected=(201,))
    log("ontology CRUD verified")

    document, _ = client.post("/v1/knowledge-bases/architecture-references/documents", {
        "title": f"M23 OpenShift reference {suffix}",
        "media_type": "text/markdown",
        "content": f"# M23 architecture\n\nThe target runtime is M23OCP{suffix}. GitOps is used for delivery.",
        "metadata": {"milestone": 23, "smoke": suffix},
    }, expected=(201,))
    doc_id = document["id"]
    client.post(f"/v1/knowledge-documents/{doc_id}/ingest", {
        "chunking_strategy": "heading",
        "metadata_enrichment": "standard",
        "embed": True,
    }, expected=(200,))
    mappings, _ = client.get(f"/v1/ontology/mappings?target_type=document&target_id={doc_id}")
    check(any(item["concept_key"] == concept_openshift for item in mappings), "Document ontology mapping was not generated")
    result, _ = client.post("/v1/knowledge/retrieve", {
        "text": f"M23 Container Platform {suffix}",
        "mode": "graph",
        "top_k": 5,
        "ontology_enabled": True,
        "ontology_max_hops": 1,
        "filters": {"knowledge_base_keys": ["architecture-references"]},
    })
    check(any(hit["document_id"] == doc_id for hit in result["hits"]), "Graph retrieval did not recover the related document")
    check(result["metadata"]["graph_candidates"] >= 1, "Graph retrieval produced no candidates")
    log("ingestion + metadata + ontology tagging + graph retrieval verified")

    scope_key = f"m23:{suffix}"
    memory, _ = client.post("/v1/memory", {
        "scope_type": "custom",
        "scope_key": scope_key,
        "kind": "decision",
        "content": "M23 smoke decision",
        "importance": 0.9,
        "metadata": {"milestone": 23},
    }, expected=(201,))
    recalled, _ = client.post("/v1/memory/recall", {
        "scopes": [{"type": "custom", "key": scope_key}],
        "kinds": ["decision"],
        "min_importance": 0,
        "limit": 10,
    })
    check(any(item["id"] == memory["id"] for item in recalled), "Memory recall did not return the stored item")
    client.delete(f"/v1/memory/{memory['id']}")
    log("memory remember/recall/forget verified")

    client.get("/v1/cache/stats")
    client.get("/v1/mcp/servers")
    log("cache + MCP registry verified")

    if real_model:
        execution, _ = client.post("/v1/executions", {
            "correlation_id": str(uuid.uuid4()),
            "agent_key": "business-analyst",
            "skill_key": "qualify-opportunity",
            "objective": "Independent platform smoke test. Return a very short validation summary.",
            "context": {
                "customer": "Milestone 23 Test",
                "evidence": "FACT: this is synthetic test data only.",
            },
            "constraints": {"smoke_test": True},
        }, expected=(202,))
        execution_id = execution["id"]
        for _ in range(60):
            current, _ = client.get(f"/v1/executions/{execution_id}")
            if current["status"] in {"COMPLETED", "FAILED", "CANCELLED"}:
                break
            import time
            time.sleep(0.5)
        check(current["status"] == "COMPLETED", f"Real model execution failed: {current}")
        result, _ = client.get(f"/v1/executions/{execution_id}/result")
        check(result["artifacts"] and result["artifacts"][0]["content"].strip(), "Real model returned empty output")
        client.get(f"/v1/executions/{execution_id}/diagnostics")
        log(f"real Anthropic execution verified ({execution_id})")
    else:
        log("real model execution skipped (use --real-model to enable paid Anthropic smoke test)")

    client.delete(f"/v1/ontology/relationships/{relationship['id']}")
    client.delete(f"/v1/ontology/concepts/{concept_openshift}")
    client.delete(f"/v1/ontology/concepts/{concept_container}")
    log("independent smoke suite PASSED")


def main() -> None:
    parser = argparse.ArgumentParser(description="Milestone 23 independent clean-room verification")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--api-key", default=os.getenv("API_KEY") or None)
    parser.add_argument("--phase", choices=("empty", "catalog", "full"), default="full")
    parser.add_argument("--real-model", action="store_true")
    args = parser.parse_args()
    client = Client(args.base_url, args.api_key)
    try:
        if args.phase == "empty":
            assert_empty(client)
        elif args.phase == "catalog":
            verify_catalog(client)
            bootstrap_knowledge(client)
        else:
            verify_catalog(client)
            bootstrap_knowledge(client)
            exercise_platform(client, args.real_model)
    except SmokeFailure as exc:
        print(f"[M23] FAILED: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
