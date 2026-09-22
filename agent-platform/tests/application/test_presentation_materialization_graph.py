import json

import pytest

from agent_platform.application.presentation_materialization_graph import (
    PresentationMaterializationError,
    _compact_template,
    _duplicate_object_ids,
    _extract_json_object,
    _operation_plan,
    _parse_duplicate_result,
    _semantic_slide_plan,
    _slide_move_steps,
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


def test_extract_json_object_accepts_markdown_fence_and_preamble():
    wrapped = """Here is the requested JSON:\n\n\`\`\`json\n{\"operations\": []}\n\`\`\`"""
    assert _extract_json_object(wrapped) == {"operations": []}


def test_default_slide_split_uses_one_slide_per_internal_call():
    plan = """# Deck\n\n## SLIDE-1\nOne\n\n## SLIDE-2\nTwo\n"""
    chunks = _split_slides_plan(plan)
    assert len(chunks) == 2
    assert "## SLIDE-1" in chunks[0]
    assert "## SLIDE-2" not in chunks[0]
    assert "## SLIDE-2" in chunks[1]


def test_semantic_slide_plan_rejects_synthetic_ids():
    inventory = json.dumps({
        "slides": [{
            "objectId": "template-slide-1",
            "elements": [{"objectId": "title-1", "kind": "shape", "text": "Template title"}],
        }]
    })
    plan = json.dumps({
        "templateSlideObjectId": "SLIDE_5_NEW",
        "texts": ["Approved title"],
    })

    with pytest.raises(PresentationMaterializationError, match="Unknown template slide objectId"):
        _semantic_slide_plan(plan, inventory)


def test_semantic_slide_plan_requires_one_text_per_template_shape():
    inventory = json.dumps({
        "slides": [{
            "objectId": "template-slide-1",
            "elements": [
                {"objectId": "title-1", "kind": "shape", "text": "Template title"},
                {"objectId": "body-1", "kind": "shape", "text": "Template body"},
            ],
        }]
    })
    plan = json.dumps({
        "templateSlideObjectId": "template-slide-1",
        "texts": ["Approved title"],
    })

    with pytest.raises(PresentationMaterializationError, match="texts\[\] length"):
        _semantic_slide_plan(plan, inventory)


def test_parse_duplicate_result_returns_real_slide_and_element_mapping():
    slide_id, mapping = _parse_duplicate_result(json.dumps({
        "objectId": "generated-slide-1",
        "objectIds": {"title-1": "generated-title-1", "body-1": "generated-body-1"},
    }))
    assert slide_id == "generated-slide-1"
    assert mapping["title-1"] == "generated-title-1"


def test_duplicate_object_ids_are_platform_owned_and_deterministic():
    plan = {
        "templateSlideObjectId": "template-slide-1",
        "elements": [
            {"templateElementObjectId": "title-1", "text": "Title"},
            {"templateElementObjectId": "body-1", "text": "Body"},
        ],
    }
    mapping = _duplicate_object_ids(plan, 5)
    assert mapping == {
        "template-slide-1": "pf_s0005",
        "title-1": "pf_s0005_e001",
        "body-1": "pf_s0005_e002",
    }


def test_compact_template_understands_mcp_summarized_elements():
    raw = json.dumps({
        "presentationId": "template-1",
        "slides": [{
            "objectId": "slide-1",
            "pageElements": [{
                "objectId": "title-1",
                "type": "shape",
                "text": "Template title",
                "shapeType": "TEXT_BOX",
            }],
        }],
        "layouts": [],
        "masters": [],
    })
    compact = json.loads(_compact_template(raw))
    element = compact["slides"][0]["elements"][0]
    assert element["kind"] == "shape"
    assert element["text"] == "Template title"
    assert element["objectId"] == "title-1"


def test_large_template_compaction_preserves_element_ids():
    raw = {
        "presentationId": "template-1",
        "slides": [],
        "layouts": [],
        "masters": [],
    }
    for slide_index in range(40):
        raw["slides"].append({
            "objectId": f"slide-{slide_index}",
            "pageElements": [
                {
                    "objectId": f"shape-{slide_index}-{element_index}",
                    "type": "shape",
                    "text": "x" * 500,
                    "shapeType": "TEXT_BOX",
                }
                for element_index in range(24)
            ],
        })
    compact = json.loads(_compact_template(json.dumps(raw)))
    assert compact["slides"][0]["elements"][0]["objectId"] == "shape-0-0"
    assert compact["slides"][39]["elements"][23]["objectId"] == "shape-39-23"


def test_semantic_slide_plan_maps_texts_to_platform_owned_element_ids():
    inventory = json.dumps({
        "slides": [{
            "objectId": "template-slide-1",
            "elements": [
                {"objectId": "title-1", "kind": "shape", "text": "Template title"},
                {"objectId": "body-1", "kind": "shape", "text": "Template body"},
                {"objectId": "image-1", "kind": "image"},
            ],
        }]
    })
    plan = json.dumps({
        "templateSlideObjectId": "template-slide-1",
        "texts": ["Approved title", "Approved body"],
    })

    semantic = _semantic_slide_plan(plan, inventory)
    assert semantic["elements"] == [
        {"templateElementObjectId": "title-1", "text": "Approved title"},
        {"templateElementObjectId": "body-1", "text": "Approved body"},
    ]


def test_semantic_slide_plan_normalizes_legacy_elements_output():
    inventory = json.dumps({
        "slides": [{
            "objectId": "template-slide-1",
            "elements": [
                {"objectId": "title-1", "kind": "shape", "text": "Template title"},
                {"objectId": "body-1", "kind": "shape", "text": "Template body"},
            ],
        }]
    })
    legacy = json.dumps({
        "templateSlideObjectId": "template-slide-1",
        "elements": [
            {"templateElementObjectId": "ignored-old-id", "text": "Approved title"},
            {"templateElementObjectId": "another-old-id", "text": "Approved body"},
        ],
    })

    semantic = _semantic_slide_plan(legacy, inventory)
    assert semantic["elements"] == [
        {"templateElementObjectId": "title-1", "text": "Approved title"},
        {"templateElementObjectId": "body-1", "text": "Approved body"},
    ]


def test_slide_move_steps_use_single_slide_requests_in_approved_order():
    assert _slide_move_steps(["pf_s0001", "pf_s0002", "pf_s0003"]) == [
        ("pf_s0001", 0),
        ("pf_s0002", 1),
        ("pf_s0003", 2),
    ]
