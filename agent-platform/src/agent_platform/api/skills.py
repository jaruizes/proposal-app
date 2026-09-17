from fastapi import APIRouter, HTTPException, Response, status

from agent_platform.api.dependencies import SkillRegistryDep
from agent_platform.application.registries import (
    DefinitionAlreadyExistsError,
    DefinitionNotFoundError,
    InvalidDefinitionReferenceError,
)
from agent_platform.domain import SkillDefinition

router = APIRouter(prefix="/v1/skills", tags=["skills"])


@router.get("", response_model=list[SkillDefinition])
async def list_skills(registry: SkillRegistryDep) -> list[SkillDefinition]:
    return await registry.list()


@router.get("/{key}", response_model=SkillDefinition)
async def get_skill(key: str, registry: SkillRegistryDep) -> SkillDefinition:
    try:
        return await registry.get(key)
    except DefinitionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("", response_model=SkillDefinition, status_code=status.HTTP_201_CREATED)
async def create_skill(skill: SkillDefinition, response: Response, registry: SkillRegistryDep) -> SkillDefinition:
    try:
        created = await registry.create(skill)
    except DefinitionAlreadyExistsError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    response.headers["Location"] = f"/v1/skills/{created.key}"
    return created


@router.put("/{key}", response_model=SkillDefinition)
async def update_skill(key: str, skill: SkillDefinition, registry: SkillRegistryDep) -> SkillDefinition:
    try:
        return await registry.update(key, skill)
    except DefinitionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except InvalidDefinitionReferenceError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
