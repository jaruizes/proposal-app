"""memory foundation

Revision ID: 0005_memory
Revises: 0004_knowledge_fts
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0005_memory"
down_revision = "0004_knowledge_fts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "memory_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("scope_type", sa.String(length=50), nullable=False),
        sa.Column("scope_key", sa.String(length=300), nullable=False),
        sa.Column("kind", sa.String(length=50), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("agent_key", sa.String(length=200), nullable=True),
        sa.Column("skill_key", sa.String(length=200), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("importance", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_memory_entries_scope", "memory_entries", ["scope_type", "scope_key"])
    op.create_index("ix_memory_entries_agent_key", "memory_entries", ["agent_key"])
    op.create_index("ix_memory_entries_created_at", "memory_entries", ["created_at"])
    op.create_index("ix_memory_entries_active", "memory_entries", ["active"])


def downgrade() -> None:
    op.drop_index("ix_memory_entries_active", table_name="memory_entries")
    op.drop_index("ix_memory_entries_created_at", table_name="memory_entries")
    op.drop_index("ix_memory_entries_agent_key", table_name="memory_entries")
    op.drop_index("ix_memory_entries_scope", table_name="memory_entries")
    op.drop_table("memory_entries")
