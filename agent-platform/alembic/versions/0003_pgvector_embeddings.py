"""pgvector embeddings
Revision ID: 0003_pgvector_embeddings
Revises: 0002_knowledge_foundation
"""
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
revision="0003_pgvector_embeddings"; down_revision="0002_knowledge_foundation"; branch_labels=None; depends_on=None
def upgrade()->None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.add_column("knowledge_chunks",sa.Column("embedding",Vector(384),nullable=True))
    op.add_column("knowledge_chunks",sa.Column("embedding_model",sa.String(200),nullable=True))
    op.create_index("ix_knowledge_chunks_embedding_hnsw","knowledge_chunks",["embedding"],postgresql_using="hnsw",postgresql_ops={"embedding":"vector_cosine_ops"})
def downgrade()->None:
    op.drop_index("ix_knowledge_chunks_embedding_hnsw",table_name="knowledge_chunks")
    op.drop_column("knowledge_chunks","embedding_model")
    op.drop_column("knowledge_chunks","embedding")
