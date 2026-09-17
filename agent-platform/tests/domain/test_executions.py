from uuid import uuid4

import pytest
from pydantic import ValidationError

from agent_platform.domain.executions import (
    AgentArtifact,
    AgentError,
    AgentExecution,
    AgentExecutionRequest,
    AgentExecutionResult,
    AgentUsage,
    Attachment,
    ExecutionStatus,
)


def test_execution_request_is_runtime_and_provider_neutral() -> None:
    correlation_id = uuid4()
    request = AgentExecutionRequest(
        correlation_id=correlation_id,
        agent_key="business-analyst",
        skill_key="analyze-opportunity",
        objective="Analyze the opportunity.",
        context={"offer_id": "offer-123"},
        attachments=[Attachment(name="rfp.pdf", media_type="application/pdf", uri="s3://bucket/rfp.pdf")],
    )

    assert request.correlation_id == correlation_id
    assert request.context["offer_id"] == "offer-123"
    assert request.attachments[0].uri == "s3://bucket/rfp.pdf"


def test_usage_accounts_for_cache_tokens_without_provider_coupling() -> None:
    usage = AgentUsage(input_tokens=100, output_tokens=25, cache_read_tokens=40, cache_write_tokens=10)

    assert usage.total_tokens == 175


def test_execution_and_result_support_success_contract() -> None:
    execution = AgentExecution(
        agent_key="solution-architect",
        skill_key="define-solution",
        objective="Define the solution architecture.",
        status=ExecutionStatus.RUNNING,
    )
    usage = AgentUsage(input_tokens=1200, output_tokens=350)
    result = AgentExecutionResult(
        execution_id=execution.id,
        status=ExecutionStatus.COMPLETED,
        artifacts=[AgentArtifact(type="SOLUTION", content="# Solution")],
        usage=usage,
        model="claude-sonnet-4-6",
        trace_id="trace-123",
    )

    assert result.execution_id == execution.id
    assert result.status is ExecutionStatus.COMPLETED
    assert result.artifacts[0].type == "SOLUTION"
    assert result.usage.total_tokens == 1550


def test_execution_result_can_expose_structured_failure() -> None:
    result = AgentExecutionResult(
        execution_id=uuid4(),
        status=ExecutionStatus.FAILED,
        error=AgentError(code="MODEL_TIMEOUT", message="Model invocation timed out", retryable=True),
    )

    assert result.error is not None
    assert result.error.retryable is True


def test_negative_token_usage_is_rejected() -> None:
    with pytest.raises(ValidationError):
        AgentUsage(input_tokens=-1)
