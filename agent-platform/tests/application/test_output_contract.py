import pytest

from agent_platform.application.models import ModelProviderError
from agent_platform.application.output_contract import normalize_output
from agent_platform.domain import AgentExecutionRequest


def request(output_format: str) -> AgentExecutionRequest:
    return AgentExecutionRequest(agent_key="delivery-manager", objective="Draft", constraints={"output_format": output_format})


def test_markdown_document_after_filename_heading_and_inner_code_fence():
    fence = chr(96) * 3
    raw = f"# delivery-plan.md\n\n{fence}markdown\n# Plan de ejecución\n\n{fence}json\n{{}}\n{fence}\n{fence}"
    assert normalize_output(request("markdown"), raw) == f"# Plan de ejecución\n\n{fence}json\n{{}}\n{fence}"


def test_raw_markdown_and_optional_none():
    assert normalize_output(request("markdown"), "# Solution\nContent") == "# Solution\nContent"
    assert normalize_output(request("optional_markdown"), " NONE ") == "NONE"


@pytest.mark.parametrize("raw", ['{"solution":"# Solution"}', chr(96) * 3 + "markdown\n# Incomplete"])
def test_invalid_markdown_is_not_published(raw):
    with pytest.raises(ModelProviderError, match="Markdown"):
        normalize_output(request("markdown"), raw)


def test_json_is_validated_and_unwrapped():
    fence = chr(96) * 3
    assert normalize_output(request("json"), f'{fence}json\n{{"sourceReview":[]}}\n{fence}') == '{"sourceReview": []}'
    with pytest.raises(ModelProviderError, match="JSON"):
        normalize_output(request("json"), '{"sourceReview":')
