"""knowledge full text search index

Revision ID: 0004_knowledge_fts
Revises: 0003_pgvector_embeddings
"""
from alembic import op

revision = "0004_knowledge_fts"
down_revision = "0003_pgvector_embeddings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_knowledge_chunks_content_fts "
        "ON knowledge_chunks USING gin (to_tsvector('simple'::regconfig, content))"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_knowledge_chunks_content_fts")
