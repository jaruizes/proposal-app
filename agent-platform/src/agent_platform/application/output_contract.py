"""Validate declared result formats before publishing an agent execution."""
import json
import re

from agent_platform.application.models import ModelProviderError
from agent_platform.domain import AgentExecutionRequest

_FENCE = re.compile(r"^```(?:markdown|md)?[ \t]*\n(?P<body>[\s\S]*?)\n```[ \t]*$", re.I)
_FILENAME = re.compile(r"^# [A-Za-z0-9][A-Za-z0-9._-]*\.md[ \t]*\n+", re.I)


def output_media_type(request: AgentExecutionRequest, content: str) -> str:
    format_name = request.constraints.get("output_format", "text")
    if format_name == "json":
        return "application/json"
    if format_name == "text" or (format_name == "optional_markdown" and content == "NONE"):
        return "text/plain"
    return "text/markdown"


def normalize_output(request: AgentExecutionRequest, raw: str) -> str:
    format_name = request.constraints.get("output_format", "text")
    if format_name not in {"markdown", "optional_markdown", "json", "text"}:
        raise ModelProviderError("INVALID_OUTPUT_FORMAT", f"Unknown output format: {format_name}")
    if format_name == "text":
        return raw.strip()
    content = raw.strip()
    if format_name == "optional_markdown" and content == "NONE":
        return content
    if format_name == "json":
        if content.startswith("```json\n") and content.endswith("\n```"):
            content = content[8:-4].strip()
        try:
            value = json.loads(content)
        except (ValueError, TypeError) as exc:
            raise ModelProviderError("INVALID_AGENT_OUTPUT", "Expected a complete JSON response") from exc
        if not isinstance(value, dict):
            raise ModelProviderError("INVALID_AGENT_OUTPUT", "Expected a JSON object")
        return json.dumps(value, ensure_ascii=False)

    # Only remove a filename heading when followed by a complete document fence.
    without_filename = _FILENAME.sub("", content, count=1)
    match = _FENCE.fullmatch(without_filename)
    if match:
        content = match.group("body").strip()
    elif without_filename != content or content.startswith("```"):
        raise ModelProviderError("INVALID_AGENT_OUTPUT", "Expected a complete Markdown document")
    if not re.match(r"^# [^\n]+\n", content) or content.startswith("# {"):
        raise ModelProviderError("INVALID_AGENT_OUTPUT", "Expected raw Markdown starting with a document heading")
    return content
