from __future__ import annotations

import hashlib
import re
from collections import Counter
from enum import StrEnum
from typing import Protocol

from agent_platform.domain import KnowledgeChunk, KnowledgeDocument


class MetadataEnrichmentProfile(StrEnum):
    NONE = "none"
    BASIC = "basic"
    STANDARD = "standard"


class MetadataEnricher(Protocol):
    async def enrich_document(self, document: KnowledgeDocument, content: str, *, profile: MetadataEnrichmentProfile, max_keywords: int) -> dict: ...
    async def enrich_chunk(self, document: KnowledgeDocument, chunk: KnowledgeChunk, *, profile: MetadataEnrichmentProfile, max_keywords: int, document_enrichment: dict) -> dict: ...


class DeterministicMetadataEnricher:
    """Deterministic enrichment with proposal-aware semantic metadata for reference material."""

    VERSION = "deterministic-v2"
    PROPOSAL_TAXONOMY_VERSION = "proposal-sections-v1"
    _TOKEN = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ0-9][A-Za-zÀ-ÖØ-öø-ÿ0-9_-]{1,}", re.UNICODE)
    _HEADING = re.compile(r"(?m)^(#{1,6})\s+(.+?)\s*$")
    _STOPWORDS = {
        "en": {
            "the","and","for","with","that","this","from","into","are","was","were","will","have","has","had","not","but","can","our","your","their","about","using","use","used","than","then","when","where","which","who","what","how","all","any","each","its","also","such","these","those","been","being","would","should","could","must",
        },
        "es": {
            "que","los","las","del","por","para","con","una","uno","unos","unas","como","más","pero","sus","este","esta","estos","estas","entre","desde","sobre","cuando","donde","todo","toda","todos","todas","también","ser","son","fue","han","hay","sin","cada","se","al","lo","un","y","o","de","la","el","en","es","a",
        },
    }
    _PROPOSAL_SECTIONS = (
        ("EXECUTIVE_SUMMARY","BUSINESS",("resumen ejecutivo","executive summary","propuesta de valor","value proposition")),
        ("CUSTOMER_CONTEXT","BUSINESS",("contexto","antecedentes","situación actual","situacion actual","reto","challenge","background")),
        ("OBJECTIVES","BUSINESS",("objetivo","objetivos","objectives","goals")),
        ("SCOPE_REQUIREMENTS","BUSINESS",("alcance","requisito","requisitos","requirements","scope","consideraciones","condicionantes")),
        ("SECURITY","TECHNICAL",("seguridad","security","rgpd","gdpr","dora","iam","cifrado","encryption","identity")),
        ("DATA_AI","TECHNICAL",("inteligencia artificial","artificial intelligence","machine learning","genai","llm","rag","datos","data platform","vector")),
        ("ARCHITECTURE","TECHNICAL",("arquitectura","architecture","openshift","kubernetes","componentes","components","integraciones","integrations","plataforma")),
        ("DELIVERY_PLAN","DELIVERY",("planificación","planificacion","fases","metodología","metodologia","delivery","workstream","cronograma","roadmap","entregables")),
        ("TEAM_GOVERNANCE","GOVERNANCE",("equipo","gobierno","governance","roles","organización","organizacion","dedicación","dedicacion")),
        ("QUALITY_TESTING","DELIVERY",("calidad","quality","pruebas","testing","qa","test strategy")),
        ("RISKS_ASSUMPTIONS","GOVERNANCE",("riesgos","risk","supuestos","assumptions","dependencias","dependencies")),
        ("VALUE_ADDED","BUSINESS",("valor añadido","valor agregado","value added","acelerador","accelerator","capacidad diferencial")),
        ("COMMERCIAL","COMMERCIAL",("precio","pricing","pagos","payment","económico","economico","coste","cost","tarifa","días/hombre","dias/hombre")),
        ("CREDENTIALS","BUSINESS",("experiencia","credentials","credenciales","certificaciones","certifications","casos de éxito","casos de exito","case studies")),
        ("NEXT_STEPS","BUSINESS",("próximos pasos","proximos pasos","next steps")),
    )

    async def enrich_document(self, document, content, *, profile, max_keywords) -> dict:
        if profile is MetadataEnrichmentProfile.NONE:
            return {}
        language = self._detect_language(content)
        enrichment = self._base(content, language, profile)
        enrichment["media_type"] = document.media_type
        if profile is MetadataEnrichmentProfile.STANDARD:
            enrichment["keywords"] = self._keywords(content, language, max_keywords)
            enrichment["headings"] = [{"level": len(match.group(1)), "text": match.group(2).strip()} for match in self._HEADING.finditer(content)][:50]
            if self._is_proposal_reference(document):
                enrichment["proposal_reference"] = True
                enrichment["proposal_taxonomy_version"] = self.PROPOSAL_TAXONOMY_VERSION
                enrichment["content_role"] = "REFERENCE_PATTERN"
        return enrichment

    async def enrich_chunk(self, document, chunk, *, profile, max_keywords, document_enrichment) -> dict:
        if profile is MetadataEnrichmentProfile.NONE:
            return {}
        language = document_enrichment.get("language") or self._detect_language(chunk.content)
        enrichment = self._base(chunk.content, language, profile)
        enrichment["sentence_count"] = len(re.findall(r"(?<=[.!?])\s+", chunk.content)) + (1 if chunk.content.strip() else 0)
        if profile is MetadataEnrichmentProfile.STANDARD:
            enrichment["keywords"] = self._keywords(chunk.content, language, max_keywords)
            enrichment["document_keywords"] = document_enrichment.get("keywords", [])
            if self._is_proposal_reference(document):
                section_type, dimension, confidence = self._proposal_section(chunk.content)
                enrichment.update({
                    "proposal_reference": True,
                    "proposal_taxonomy_version": self.PROPOSAL_TAXONOMY_VERSION,
                    "content_role": "REFERENCE_PATTERN",
                    "section_type": section_type,
                    "proposal_dimension": dimension,
                    "section_confidence": confidence,
                })
        return enrichment

    def _base(self, content: str, language: str, profile: MetadataEnrichmentProfile) -> dict:
        words = self._TOKEN.findall(content)
        return {"version":self.VERSION,"profile":profile.value,"language":language,"char_count":len(content),"word_count":len(words),"content_hash":hashlib.sha256(content.encode("utf-8")).hexdigest()}

    def _detect_language(self, content: str) -> str:
        tokens = [token.lower() for token in self._TOKEN.findall(content)]
        if not tokens:return "undetermined"
        sample=tokens[:2000];en=sum(token in self._STOPWORDS["en"] for token in sample);es=sum(token in self._STOPWORDS["es"] for token in sample)
        if en==es==0:return "undetermined"
        return "es" if es>en else "en"

    def _keywords(self, content: str, language: str, limit: int) -> list[str]:
        if limit<=0:return []
        stopwords=self._STOPWORDS.get(language,set())|self._STOPWORDS["en"]|self._STOPWORDS["es"]
        tokens=[token.lower() for token in self._TOKEN.findall(content)]
        candidates=[token for token in tokens if len(token)>=3 and token not in stopwords and not token.isdigit()]
        counts=Counter(candidates);first_position={}
        for index,token in enumerate(candidates):first_position.setdefault(token,index)
        return sorted(counts,key=lambda token:(-counts[token],first_position[token],token))[:limit]

    @staticmethod
    def _is_proposal_reference(document: KnowledgeDocument) -> bool:
        classification=document.metadata.get("classification",{})
        document_type=classification.get("document_type") if isinstance(classification,dict) else None
        return document.knowledge_base_key=="reference-offers" or document_type=="REFERENCE_PROPOSAL" or bool(document.metadata.get("proposal_type"))

    def _proposal_section(self, content: str) -> tuple[str,str,float]:
        text=" ".join(content.lower().split())
        scored=[]
        for order,(section,dimension,terms) in enumerate(self._PROPOSAL_SECTIONS):
            matches=sum(text.count(term) for term in terms)
            if matches:scored.append((matches,-order,section,dimension))
        if not scored:return "GENERAL","GENERAL",0.0
        matches,_,section,dimension=max(scored)
        confidence=min(1.0,0.45+0.15*matches)
        return section,dimension,round(confidence,2)


__all__=["DeterministicMetadataEnricher","MetadataEnricher","MetadataEnrichmentProfile"]
