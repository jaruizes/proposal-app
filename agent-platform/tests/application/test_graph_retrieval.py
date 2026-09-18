from uuid import uuid4

import pytest

from agent_platform.application.ontology import OntologyQueryContext
from agent_platform.application.retrieval import KnowledgeRetrievalService, RetrievalCandidate
from agent_platform.application.embeddings import EmbeddingResult
from agent_platform.domain import RetrievalMode, RetrievalQuery


class Embeddings:
    provider_key="fake";model="fake";dimensions=2
    async def embed(self,request):return EmbeddingResult(vectors=[[1.0,0.0]],model=self.model,dimensions=2)


class Ontology:
    async def resolve_query(self,text,*,max_hops,max_concepts):
        return OntologyQueryContext(seed_concepts=["platform.kubernetes"],concept_weights={"platform.kubernetes":1.0,"technology.openshift":0.7},max_hops=max_hops)


class Backend:
    def __init__(self):
        self.vector_id=uuid4();self.keyword_id=uuid4();self.graph_id=uuid4();self.document_id=uuid4()
    def item(self,chunk_id,label,score,graph=False):
        return RetrievalCandidate(chunk_id=chunk_id,document_id=self.document_id,knowledge_base_key="kb",title="Doc",content=label,score=score,metadata={"graph_match":True} if graph else {})
    async def vector_search(self,**kwargs):return[self.item(self.vector_id,"vector",.9)]
    async def keyword_search(self,**kwargs):return[self.item(self.keyword_id,"keyword",.8)]
    async def ontology_search(self,**kwargs):
        assert kwargs["concept_weights"]["technology.openshift"]==0.7
        return[self.item(self.graph_id,"graph",1.2,True)]
    async def parent_for(self,candidate):return None


@pytest.mark.asyncio
async def test_hybrid_retrieval_fuses_graph_candidates_and_exposes_ontology_context():
    service=KnowledgeRetrievalService(Backend(),Embeddings(),ontology_service=Ontology())
    result=await service.retrieve(RetrievalQuery(text="Kubernetes platform",mode=RetrievalMode.HYBRID,top_k=3))
    assert {hit.content for hit in result.hits}=={"vector","keyword","graph"}
    assert all(hit.retrieval_method is RetrievalMode.HYBRID for hit in result.hits)
    assert result.metadata["fusion"]=="rrf-v2-graph-aware"
    assert result.metadata["ontology_seed_concepts"]==["platform.kubernetes"]
    assert result.metadata["ontology_expanded_concepts"]==["technology.openshift"]
    assert result.metadata["graph_candidates"]==1


@pytest.mark.asyncio
async def test_graph_mode_uses_ontology_without_embedding_or_keyword():
    class NoEmbeddings:
        provider_key="none";model="none";dimensions=0
        async def embed(self,request):raise AssertionError("embedding must not be called")
    backend=Backend();service=KnowledgeRetrievalService(backend,NoEmbeddings(),ontology_service=Ontology())
    result=await service.retrieve(RetrievalQuery(text="Kubernetes",mode=RetrievalMode.GRAPH,top_k=1))
    assert result.hits[0].content=="graph"
    assert result.hits[0].retrieval_method is RetrievalMode.GRAPH
