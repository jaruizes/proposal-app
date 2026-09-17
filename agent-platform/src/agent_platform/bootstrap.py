from __future__ import annotations

import argparse
import asyncio
import json
from importlib import resources
from typing import Any

from agent_platform.application.registries import AgentRegistry, SkillRegistry
from agent_platform.domain import AgentDefinition, SkillDefinition
from agent_platform.persistence.database import SessionFactory
from agent_platform.persistence.repositories import PostgresAgentRepository, PostgresSkillRepository


BOOTSTRAP_ROOT = resources.files("agent_platform").joinpath("bootstrap_data")


def _parse_frontmatter(markdown: str) -> dict[str, str]:
    lines = markdown.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    metadata: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        metadata[key.strip()] = value.strip()
    return metadata


def _first_heading(markdown: str, fallback: str) -> str:
    for line in markdown.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return fallback


def _read_text(root: Any, relative_path: str) -> str:
    return root.joinpath(*relative_path.split("/")).read_text(encoding="utf-8")


def load_bootstrap_catalog(root: Any = BOOTSTRAP_ROOT) -> tuple[list[SkillDefinition], list[AgentDefinition]]:
    """Load the Git-tracked Proposal Copilot definitions into provider-neutral domain objects."""

    manifest = json.loads(_read_text(root, "manifest.json"))

    skills: list[SkillDefinition] = []
    for item in manifest["skills"]:
        markdown = _read_text(root, item["source"])
        frontmatter = _parse_frontmatter(markdown)
        description = frontmatter.get("description", "")
        skills.append(
            SkillDefinition(
                key=item["key"],
                name=item.get("name") or _first_heading(markdown, item["key"]),
                description=description,
                objective=item.get("objective") or description or item["key"],
                instructions=markdown,
                inputs=item.get("inputs", []),
                output_schema=item.get("output_schema", {}),
                knowledge_sources=item.get("knowledge_sources", []),
                allowed_tools=item.get("allowed_tools", []),
                constraints=item.get("constraints", {}),
                enabled=item.get("enabled", True),
            )
        )

    agents: list[AgentDefinition] = []
    for item in manifest["agents"]:
        markdown = _read_text(root, item["source"])
        frontmatter = _parse_frontmatter(markdown)
        agents.append(
            AgentDefinition(
                key=item["key"],
                name=item.get("name") or _first_heading(markdown, item["key"]),
                description=frontmatter.get("description", ""),
                role=markdown,
                capabilities=item.get("capabilities", []),
                skills=item.get("skills", []),
                knowledge_scopes=item.get("knowledge_scopes", []),
                allowed_tools=item.get("allowed_tools", []),
                model_policy=item.get("model_policy", {}),
                constraints=item.get("constraints", {}),
                enabled=item.get("enabled", True),
            )
        )

    return skills, agents


def _same_definition(current: Any, desired: Any) -> bool:
    return current.model_dump(exclude={"id", "version"}, mode="json") == desired.model_dump(
        exclude={"id", "version"}, mode="json"
    )


class BootstrapImporter:
    """Import Git bootstrap definitions while keeping runtime DB configuration authoritative by default."""

    def __init__(self, skills: SkillRegistry, agents: AgentRegistry) -> None:
        self._skills = skills
        self._agents = agents

    async def import_all(self, *, sync: bool = False) -> dict[str, dict[str, list[str]]]:
        skill_definitions, agent_definitions = load_bootstrap_catalog()
        report = {
            "skills": {"created": [], "updated": [], "skipped": []},
            "agents": {"created": [], "updated": [], "skipped": []},
        }

        # Skills must exist before agents because AgentRegistry validates skill references.
        for desired in skill_definitions:
            current = await self._skills.find(desired.key)
            if current is None:
                await self._skills.create(desired)
                report["skills"]["created"].append(desired.key)
            elif sync and not _same_definition(current, desired):
                await self._skills.update(desired.key, desired)
                report["skills"]["updated"].append(desired.key)
            else:
                report["skills"]["skipped"].append(desired.key)

        for desired in agent_definitions:
            current = await self._agents.find(desired.key)
            if current is None:
                await self._agents.create(desired)
                report["agents"]["created"].append(desired.key)
            elif sync and not _same_definition(current, desired):
                await self._agents.update(desired.key, desired)
                report["agents"]["updated"].append(desired.key)
            else:
                report["agents"]["skipped"].append(desired.key)

        return report


async def _run(sync: bool) -> dict[str, dict[str, list[str]]]:
    async with SessionFactory() as session:
        skill_repository = PostgresSkillRepository(session)
        agent_repository = PostgresAgentRepository(session)
        importer = BootstrapImporter(
            SkillRegistry(skill_repository),
            AgentRegistry(agent_repository, skill_repository),
        )
        return await importer.import_all(sync=sync)


def main() -> None:
    parser = argparse.ArgumentParser(description="Import the Git-tracked Agent Platform bootstrap catalog.")
    parser.add_argument(
        "--sync",
        action="store_true",
        help="Update existing DB definitions when Git bootstrap content differs. Without this flag, existing DB definitions are preserved.",
    )
    args = parser.parse_args()
    report = asyncio.run(_run(args.sync))
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
