import json
from pathlib import Path

import pytest

from agent_platform.application.proposal_retrieval import ProposalReferenceRetriever


CASES = json.loads((Path(__file__).parent / "proposal_retrieval_cases.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("case", CASES)
def test_proposal_section_classifier_evaluation_cases(case):
    predicted = ProposalReferenceRetriever.classify_section(case["query"])
    assert predicted == case["section_type"]


def test_evaluation_suite_contains_negative_control():
    negatives = [case for case in CASES if not case["should_match"]]
    assert negatives
    assert any(case["query"] == "caca" for case in negatives)


class RecordingService:
    def __init__(self):
        self.queries=[]

    async def retrieve(self, query):
        from agent_platform.domain import RetrievalResult
        self.queries.append(query)
        return RetrievalResult(query=query.text, mode=query.mode, hits=[], metadata={"relevance_filtering": True})


@pytest.mark.asyncio
async def test_section_retriever_targets_reference_offers_and_section_metadata():
    service=RecordingService()
    retriever=ProposalReferenceRetriever(service)

    section_type, refs, metadata=await retriever.retrieve(
        section_name="Arquitectura e integraciones",
        guidance="Describir componentes y seguridad",
        objective="Responder al RFP",
        top_k=3,
    )

    assert section_type=="ARCHITECTURE"
    assert refs==[]
    assert service.queries[0].filters.knowledge_base_keys==["reference-offers"]
    assert service.queries[0].filters.metadata["enrichment"]["section_type"]=="ARCHITECTURE"
    # No section match triggers a safe second pass in the same reference base.
    assert service.queries[-1].filters.knowledge_base_keys==["reference-offers"]


@pytest.mark.asyncio
async def test_negative_control_never_broadens_beyond_reference_offers():
    service=RecordingService()
    retriever=ProposalReferenceRetriever(service)

    section_type, refs, _=await retriever.retrieve(
        section_name="caca",
        guidance="",
        objective="",
        top_k=3,
    )

    assert section_type=="GENERAL"
    assert refs==[]
    assert len(service.queries)==1
    assert service.queries[0].filters.knowledge_base_keys==["reference-offers"]
