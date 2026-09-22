import json

import pytest

from agent_platform.application.presentation_materialization_graph import (
    PresentationMaterializationError,
    _compact_template,
    _operation_plan,
    _split_slides_plan,
)


def test_split_slides_plan_is_internal_and_bounded():
    plan = """# SSIR

# SECTION-1 — Contexto

## SLIDE-1
### Título de slide
Uno

## SLIDE-2
### Título de slide
Dos

## SLIDE-3
### Título de slide
Tres

# SECTION-2 — Solución

## SLIDE-4
### Título de slide
Cuatro

## SLIDE-5
### Título de slide
Cinco
"""
    chunks = _split_slides_plan(plan, max_slides=3)
    assert len(chunks) == 2
    assert "## SLIDE-1" in chunks[0]
    assert "## SLIDE-3" in chunks[0]
    assert "# SECTION-2" not in chunks[0]
    assert "# SECTION-2" in chunks[1]
    assert "## SLIDE-4" in chunks[1]
    assert "## SLIDE-5" in chunks[1]


def test_template_compaction_keeps_mcp_payload_small():
    raw = {
        "presentationId": "template-1",
        "title": "Corporate",
        "slides": [],
        "layouts": [],
        "masters": [{"objectId": "master-1"}],
    }
    for slide_index in range(25):
        raw["slides"].append({
            "objectId": f"slide-{slide_index}",
            "slideProperties": {"layoutObjectId": "layout-1"},
            "pageElements": [
                {
                    "objectId": f"shape-{slide_index}-{element_index}",
                    "shape": {
                        "shapeType": "TEXT_BOX",
                        "text": {"textElements": [{"textRun": {"content": "x" * 5000}}]},
                    },
                    "heavy": "y" * 5000,
                }
                for element_index in range(20)
            ],
        })
    raw["layouts"].append({
        "objectId": "layout-1",
        "layoutProperties": {"name": "Title", "masterObjectId": "master-1"},
    })

    raw_text = json.dumps(raw)
    assert len(raw_text) > 1_000_000

    compact = _compact_template(raw_text)
    assert len(compact) < 200_000
    assert "template-1" in compact
    assert "slide-0" in compact
    assert "shape-0-0" in compact
    assert '"heavy"' not in compact


def test_operation_plan_rejects_replace_text_without_required_contract_fields():
    content = json.dumps({
        "operations": [
            {
                "tool": "slides_replace_text",
                "arguments": {"presentationId": "$PRESENTATION_ID"},
            }
        ]
    })

    with pytest.raises(PresentationMaterializationError, match=r"pageObjectIds"):
        _operation_plan(content)


def test_operation_plan_accepts_replace_text_contract_without_presentation_id():
    content = json.dumps({
        "operations": [
            {
                "tool": "slides_replace_text",
                "arguments": {
                    "pageObjectIds": ["slide-1"],
                    "replacements": [{"from": "Old", "to": "New", "matchCase": True}],
                },
            }
        ]
    })

    operations = _operation_plan(content)
    assert operations[0]["arguments"]["pageObjectIds"] == ["slide-1"]
