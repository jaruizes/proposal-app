from __future__ import annotations

from uuid import UUID

from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_platform.application.ontology import OntologyRepository
from agent_platform.domain.ontology import OntologyConcept, OntologyMapping, OntologyRelationship, OntologyTargetType
from agent_platform.persistence.models import OntologyAliasRecord, OntologyConceptRecord, OntologyMappingRecord, OntologyRelationshipRecord


def _concept(r):
    return OntologyConcept(id=r.id,key=r.key,name=r.name,type=r.type,description=r.description,aliases=[a.value for a in r.aliases],metadata=r.metadata_json or {},enabled=r.enabled,created_at=r.created_at)
def _relationship(r):
    return OntologyRelationship(id=r.id,source_key=r.source_key,relation=r.relation,target_key=r.target_key,metadata=r.metadata_json or {},created_at=r.created_at)
def _mapping(r):
    return OntologyMapping(id=r.id,target_type=OntologyTargetType(r.target_type),target_id=r.target_id,concept_key=r.concept_key,confidence=r.confidence,source=r.source,metadata=r.metadata_json or {},created_at=r.created_at)


class PostgresOntologyRepository(OntologyRepository):
    def __init__(self,session:AsyncSession)->None:self.session=session

    async def list_concepts(self,concept_type=None):
        stmt=select(OntologyConceptRecord).order_by(OntologyConceptRecord.key)
        if concept_type: stmt=stmt.where(OntologyConceptRecord.type==concept_type)
        result=await self.session.execute(stmt); return [_concept(r) for r in result.scalars().unique().all()]

    async def get_concept(self,key):
        result=await self.session.execute(select(OntologyConceptRecord).where(OntologyConceptRecord.key==key));r=result.scalars().unique().one_or_none();return _concept(r) if r else None

    async def create_concept(self,item):
        self.session.add(OntologyConceptRecord(id=item.id,key=item.key,name=item.name,type=item.type,description=item.description,metadata_json=item.metadata,enabled=item.enabled,created_at=item.created_at,aliases=[OntologyAliasRecord(value=a) for a in sorted(set(item.aliases))]));await self.session.commit();return item

    async def update_concept(self,item):
        result=await self.session.execute(select(OntologyConceptRecord).where(OntologyConceptRecord.key==item.key));r=result.scalars().unique().one();r.name=item.name;r.type=item.type;r.description=item.description;r.metadata_json=item.metadata;r.enabled=item.enabled;r.aliases=[OntologyAliasRecord(value=a) for a in sorted(set(item.aliases))];await self.session.commit();return item

    async def delete_concept(self,key):
        await self.session.execute(delete(OntologyConceptRecord).where(OntologyConceptRecord.key==key));await self.session.commit()

    async def list_relationships(self,concept_key=None):
        stmt=select(OntologyRelationshipRecord).order_by(OntologyRelationshipRecord.source_key,OntologyRelationshipRecord.relation,OntologyRelationshipRecord.target_key)
        if concept_key: stmt=stmt.where(or_(OntologyRelationshipRecord.source_key==concept_key,OntologyRelationshipRecord.target_key==concept_key))
        result=await self.session.execute(stmt);return [_relationship(r) for r in result.scalars().all()]

    async def create_relationship(self,item):
        self.session.add(OntologyRelationshipRecord(id=item.id,source_key=item.source_key,relation=item.relation,target_key=item.target_key,metadata_json=item.metadata,created_at=item.created_at));await self.session.commit();return item

    async def delete_relationship(self,relationship_id):
        await self.session.execute(delete(OntologyRelationshipRecord).where(OntologyRelationshipRecord.id==relationship_id));await self.session.commit()

    async def replace_mappings(self,target_type,target_id,mappings):
        await self.session.execute(delete(OntologyMappingRecord).where(OntologyMappingRecord.target_type==target_type.value,OntologyMappingRecord.target_id==target_id))
        self.session.add_all([OntologyMappingRecord(id=m.id,target_type=m.target_type.value,target_id=m.target_id,concept_key=m.concept_key,confidence=m.confidence,source=m.source,metadata_json=m.metadata,created_at=m.created_at) for m in mappings]);await self.session.commit();return mappings

    async def list_mappings(self,target_type=None,target_id=None):
        stmt=select(OntologyMappingRecord).order_by(OntologyMappingRecord.created_at)
        if target_type: stmt=stmt.where(OntologyMappingRecord.target_type==target_type.value)
        if target_id: stmt=stmt.where(OntologyMappingRecord.target_id==target_id)
        result=await self.session.execute(stmt);return [_mapping(r) for r in result.scalars().all()]
