from fastapi import APIRouter, HTTPException, Response, status

from agent_platform.api.state import skills
from agent_platform.domain import SkillDefinition

router = APIRouter(prefix="/v1/skills", tags=["skills"])


@router.get("", response_model=list[SkillDefinition])
async def list_skills() -> list[SkillDefinition]:
    return list(skills.values())


@router.get("/{key}", response_model=SkillDefinition)
async def get_skill(key: str) -> SkillDefinition:
    skill = skills.get(key)
    if skill is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Skill not found")
    return skill


@router.post("", response_model=SkillDefinition, status_code=status.HTTP_201_CREATED)
async def create_skill(skill: SkillDefinition, response: Response) -> SkillDefinition:
    if skill.key in skills:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Skill already exists")
    skills[skill.key] = skill
    response.headers["Location"] = f"/v1/skills/{skill.key}"
    return skill


@router.put("/{key}", response_model=SkillDefinition)
async def update_skill(key: str, skill: SkillDefinition) -> SkillDefinition:
    if key != skill.key:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Path key must match skill key")
    if key not in skills:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Skill not found")
    skills[key] = skill
    return skill
