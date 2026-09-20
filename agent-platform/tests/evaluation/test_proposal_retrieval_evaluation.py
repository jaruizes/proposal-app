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
