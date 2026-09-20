from __future__ import annotations

from dataclasses import dataclass

from agent_platform.application.retrieval import KnowledgeRetrievalService
from agent_platform.domain import RetrievalFilters, RetrievalMode, RetrievalQuery


@dataclass(frozen=True)
class ProposalReference:
    title: str
    document_id: str
    chunk_id: str
    score: float
    content: str
    source_uri: str | None
    section_type: str


class ProposalReferenceRetriever:
    """Section-aware retrieval for proposal reference patterns."""

    _SECTION_TERMS = (
        ("EXECUTIVE_SUMMARY", ("resumen ejecutivo", "executive summary", "summary", "síntesis", "sintesis")),
        ("CUSTOMER_CONTEXT", ("contexto", "reto", "challenge", "situación", "situacion", "background")),
        ("OBJECTIVES", ("objetivo", "objetivos", "objective", "goals")),
        ("SCOPE_REQUIREMENTS", ("alcance", "requisito", "requisitos", "scope", "requirements", "condicionantes")),
        ("SECURITY", ("seguridad", "security", "iam", "rgpd", "gdpr", "dora", "cifrado")),
        ("DATA_AI", ("inteligencia artificial", "artificial intelligence", "machine learning", "genai", "llm", "rag", "datos", "data")),
        ("ARCHITECTURE", ("arquitectura", "architecture", "componentes", "components", "integraciones", "integrations", "plataforma")),
        ("DELIVERY_PLAN", ("ejecución", "ejecucion", "delivery", "planificación", "planificacion", "fases", "workstream", "entregables", "roadmap")),
        ("TEAM_GOVERNANCE", ("equipo", "team", "gobierno", "governance", "roles", "organización", "organizacion")),
        ("QUALITY_TESTING", ("calidad", "quality", "pruebas", "testing", "qa")),
        ("RISKS_ASSUMPTIONS", ("riesgos", "risk", "supuestos", "assumptions", "dependencias")),
        ("VALUE_ADDED", ("valor añadido", "valor agregado", "value added", "diferenciadores", "aceleradores")),
        ("COMMERCIAL", ("comercial", "commercial", "precio", "pricing", "coste", "payment", "pago")),
        ("CREDENTIALS", ("experiencia", "credenciales", "credentials", "certificaciones", "casos de éxito", "casos de exito", "case studies")),
        ("NEXT_STEPS", ("próximos pasos", "proximos pasos", "next steps")),
    )

    def __init__(self, service: KnowledgeRetrievalService) -> None:
        self._service = service

    @classmethod
    def classify_section(cls, name: str, guidance: str = "") -> str:
        text = f"{name} {guidance}".lower()
        scored: list[tuple[int, int, str]] = []
        for order, (section_type, terms) in enumerate(cls._SECTION_TERMS):
            score = sum(text.count(term) for term in terms)
            if score:
                scored.append((score, -order, section_type))
        return max(scored)[2] if scored else "GENERAL"

    async def retrieve(self, *, section_name: str, guidance: str, objective: str, top_k: int = 3):
        section_type = self.classify_section(section_name, guidance)
        query_text = f"{section_name}. {guidance}".strip()
        if objective:
            query_text += f"\nCurrent proposal objective: {objective}"

        metadata_filter = {} if section_type == "GENERAL" else {"enrichment": {"section_type": section_type}}
        query = RetrievalQuery(
            text=query_text,
            mode=RetrievalMode.HYBRID,
            top_k=top_k,
            candidate_k=max(20, top_k * 5),
            filters=RetrievalFilters(knowledge_base_keys=["reference-offers"], metadata=metadata_filter),
            expand_parents=True,
            vector_min_score=0.20,
            keyword_min_score=0.0,
            graph_min_score=0.0,
            ontology_enabled=True,
        )
        result = await self._service.retrieve(query)

        if not result.hits and section_type != "GENERAL":
            result = await self._service.retrieve(query.model_copy(update={
                "filters": RetrievalFilters(knowledge_base_keys=["reference-offers"])
            }))

        references = [
            ProposalReference(
                title=hit.title,
                document_id=str(hit.document_id),
                chunk_id=str(hit.chunk_id),
                score=float(hit.score),
                content=hit.parent_content or hit.content,
                source_uri=hit.source_uri,
                section_type=section_type,
            )
            for hit in result.hits
        ]
        return section_type, references, result.metadata


__all__ = ["ProposalReference", "ProposalReferenceRetriever"]
