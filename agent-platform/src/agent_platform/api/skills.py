from fastapi import APIRouter, HTTPException, Response, status

from agent_platform.api.dependencies import SkillRepositoryDep
from agent_platform.domain import SkillDefinition

router = APIRouter(prefix="/v1/skills", tags=["skills"])


@router.get("", response_model=list[SkillDefinition])
async def list_skills(repository: SkillRepositoryDep) -> list[SkillDefinition]:
    return await repository.list()


@router.get("/{key}", response_model=SkillDefinition)
async def get_skill(key: str, repository: SkillRepositoryDep) -> SkillDefinition:
    skill = await repository.get_by_key(key)
    if skill is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Skill not found")
    return skill


@router.post("", response_model=SkillDefinition, status_code=status.HTTP_201_CREATED)
async def create_skill(skill: SkillDefinition, response: Response, repository: SkillRepositoryDep) -> SkillDefinition:
    if await repository.get_by_key(skill.key) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Skill already exists")
    created = await repository.create(skill)
    response.headers["Location"] = f"/v1/skills/{skill.key}"
    return created


@router.put("/{key}", response_model=SkillDefinition)
async def update_skill(key: str, skill: SkillDefinition, repository: SkillRepositoryDep) -> SkillDefinition:
    if key != skill.key:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Path key must match skill key")
    if await repository.get_by_key(key) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Skill not found")
    return await repository.update(skill)
