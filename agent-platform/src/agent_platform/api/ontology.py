from uuid import UUID

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel, Field

from agent_platform.api.dependencies import OntologyServiceDep
from agent_platform.application.ontology import OntologyConflictError, OntologyNotFoundError
from agent_platform.domain.ontology import OntologyConcept, OntologyMapping, OntologyRelationship, OntologyTargetType

router=APIRouter(prefix="/v1/ontology",tags=["ontology"])


class ConceptWrite(BaseModel):
    key:str
    name:str
    type:str
    description:str=""
    aliases:list[str]=Field(default_factory=list)
    metadata:dict=Field(default_factory=dict)
    enabled:bool=True


class RelationshipWrite(BaseModel):
    source_key:str
    relation:str
    target_key:str
    metadata:dict=Field(default_factory=dict)


@router.get("/concepts",response_model=list[OntologyConcept])
async def list_concepts(service:OntologyServiceDep,type:str|None=None):return await service.list_concepts(type)

@router.post("/concepts",response_model=OntologyConcept,status_code=status.HTTP_201_CREATED)
async def create_concept(payload:ConceptWrite,service:OntologyServiceDep):
    try:return await service.create_concept(OntologyConcept(**payload.model_dump()))
    except OntologyConflictError as exc:raise HTTPException(status_code=409,detail=str(exc)) from exc

@router.get("/concepts/{key}",response_model=OntologyConcept)
async def get_concept(key:str,service:OntologyServiceDep):
    try:return await service.get_concept(key)
    except OntologyNotFoundError as exc:raise HTTPException(status_code=404,detail=str(exc)) from exc

@router.put("/concepts/{key}",response_model=OntologyConcept)
async def update_concept(key:str,payload:ConceptWrite,service:OntologyServiceDep):
    try:return await service.update_concept(key,OntologyConcept(**payload.model_dump()))
    except OntologyNotFoundError as exc:raise HTTPException(status_code=404,detail=str(exc)) from exc
    except OntologyConflictError as exc:raise HTTPException(status_code=409,detail=str(exc)) from exc

@router.delete("/concepts/{key}",status_code=status.HTTP_204_NO_CONTENT)
async def delete_concept(key:str,service:OntologyServiceDep):
    try:await service.delete_concept(key);return Response(status_code=204)
    except OntologyNotFoundError as exc:raise HTTPException(status_code=404,detail=str(exc)) from exc

@router.get("/relationships",response_model=list[OntologyRelationship])
async def list_relationships(service:OntologyServiceDep,concept_key:str|None=None):return await service.list_relationships(concept_key)

@router.post("/relationships",response_model=OntologyRelationship,status_code=status.HTTP_201_CREATED)
async def create_relationship(payload:RelationshipWrite,service:OntologyServiceDep):
    try:return await service.create_relationship(OntologyRelationship(**payload.model_dump()))
    except OntologyNotFoundError as exc:raise HTTPException(status_code=404,detail=str(exc)) from exc
    except OntologyConflictError as exc:raise HTTPException(status_code=409,detail=str(exc)) from exc

@router.delete("/relationships/{relationship_id}",status_code=status.HTTP_204_NO_CONTENT)
async def delete_relationship(relationship_id:UUID,service:OntologyServiceDep):
    await service.delete_relationship(relationship_id);return Response(status_code=204)

@router.get("/mappings",response_model=list[OntologyMapping])
async def list_mappings(service:OntologyServiceDep,target_type:OntologyTargetType|None=None,target_id:UUID|None=None):return await service.list_mappings(target_type,target_id)

@router.post("/tag/documents/{document_id}",response_model=list[OntologyMapping])
async def tag_document(document_id:UUID,service:OntologyServiceDep):
    try:return await service.tag_document(document_id)
    except OntologyNotFoundError as exc:raise HTTPException(status_code=404,detail=str(exc)) from exc
