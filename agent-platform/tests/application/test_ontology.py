from uuid import uuid4

import pytest

from agent_platform.application.ontology import OntologyConflictError, OntologyService
from agent_platform.domain.ontology import OntologyConcept, OntologyRelationship, OntologyTargetType


class Repo:
    def __init__(self):self.concepts={};self.relationships=[];self.mappings={}
    async def list_concepts(self,concept_type=None):return [c for c in self.concepts.values() if not concept_type or c.type==concept_type]
    async def get_concept(self,key):return self.concepts.get(key)
    async def create_concept(self,item):self.concepts[item.key]=item;return item
    async def update_concept(self,item):self.concepts[item.key]=item;return item
    async def delete_concept(self,key):self.concepts.pop(key,None)
    async def list_relationships(self,concept_key=None):return [r for r in self.relationships if not concept_key or concept_key in {r.source_key,r.target_key}]
    async def create_relationship(self,item):self.relationships.append(item);return item
    async def delete_relationship(self,relationship_id):self.relationships=[r for r in self.relationships if r.id!=relationship_id]
    async def replace_mappings(self,target_type,target_id,mappings):self.mappings[(target_type,target_id)]=mappings;return mappings
    async def list_mappings(self,target_type=None,target_id=None):return [m for (t,i),items in self.mappings.items() for m in items if (not target_type or t==target_type) and (not target_id or i==target_id)]


class Knowledge:
    async def get_document(self,_):return None
    async def list_chunks(self,_):return []


@pytest.mark.asyncio
async def test_concepts_relationships_and_alias_tagging():
    repo=Repo();service=OntologyService(repo,Knowledge())
    await service.create_concept(OntologyConcept(key="technology.openshift",name="OpenShift",type="technology",aliases=["OCP","Red Hat OpenShift"]))
    await service.create_concept(OntologyConcept(key="platform.container",name="Container Platform",type="platform"))
    relationship=await service.create_relationship(OntologyRelationship(source_key="technology.openshift",relation="IS_A",target_key="platform.container"))
    assert relationship.relation=="IS_A"
    target=uuid4();mappings=await service.tag_text(target_type=OntologyTargetType.CHUNK,target_id=target,content="The target runtime is OCP with GitOps.")
    assert [m.concept_key for m in mappings]==["technology.openshift"]
    assert mappings[0].metadata["matched_term"]=="OCP"


@pytest.mark.asyncio
async def test_duplicate_and_self_relationship_are_rejected():
    repo=Repo();service=OntologyService(repo,Knowledge())
    concept=OntologyConcept(key="technology.kafka",name="Kafka",type="technology")
    await service.create_concept(concept)
    with pytest.raises(OntologyConflictError):await service.create_concept(concept)
    with pytest.raises(OntologyConflictError):await service.create_relationship(OntologyRelationship(source_key=concept.key,relation="RELATED_TO",target_key=concept.key))
