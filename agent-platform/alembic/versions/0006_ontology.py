"""ontology foundation

Revision ID: 0006_ontology
Revises: 0005_memory
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision="0006_ontology"
down_revision="0005_memory"
branch_labels=None
depends_on=None


def upgrade()->None:
    op.create_table("ontology_concepts",
        sa.Column("id",postgresql.UUID(as_uuid=True),primary_key=True),
        sa.Column("key",sa.String(200),nullable=False,unique=True),
        sa.Column("name",sa.String(300),nullable=False),
        sa.Column("type",sa.String(100),nullable=False),
        sa.Column("description",sa.Text(),nullable=False,server_default=""),
        sa.Column("metadata",postgresql.JSONB(),nullable=False,server_default=sa.text("'{}'::jsonb")),
        sa.Column("enabled",sa.Boolean(),nullable=False,server_default=sa.true()),
        sa.Column("created_at",sa.DateTime(timezone=True),nullable=False))
    op.create_index("ix_ontology_concepts_type","ontology_concepts",["type"])
    op.create_table("ontology_aliases",
        sa.Column("id",postgresql.UUID(as_uuid=True),primary_key=True),
        sa.Column("concept_key",sa.String(200),sa.ForeignKey("ontology_concepts.key",ondelete="CASCADE"),nullable=False),
        sa.Column("value",sa.String(300),nullable=False),
        sa.UniqueConstraint("concept_key","value",name="uq_ontology_alias"))
    op.create_table("ontology_relationships",
        sa.Column("id",postgresql.UUID(as_uuid=True),primary_key=True),
        sa.Column("source_key",sa.String(200),sa.ForeignKey("ontology_concepts.key",ondelete="CASCADE"),nullable=False),
        sa.Column("relation",sa.String(100),nullable=False),
        sa.Column("target_key",sa.String(200),sa.ForeignKey("ontology_concepts.key",ondelete="CASCADE"),nullable=False),
        sa.Column("metadata",postgresql.JSONB(),nullable=False,server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at",sa.DateTime(timezone=True),nullable=False),
        sa.UniqueConstraint("source_key","relation","target_key",name="uq_ontology_relationship"))
    op.create_index("ix_ontology_relationship_source","ontology_relationships",["source_key"])
    op.create_index("ix_ontology_relationship_target","ontology_relationships",["target_key"])
    op.create_table("ontology_mappings",
        sa.Column("id",postgresql.UUID(as_uuid=True),primary_key=True),
        sa.Column("target_type",sa.String(50),nullable=False),
        sa.Column("target_id",postgresql.UUID(as_uuid=True),nullable=False),
        sa.Column("concept_key",sa.String(200),sa.ForeignKey("ontology_concepts.key",ondelete="CASCADE"),nullable=False),
        sa.Column("confidence",sa.Float(),nullable=False,server_default="1.0"),
        sa.Column("source",sa.String(100),nullable=False),
        sa.Column("metadata",postgresql.JSONB(),nullable=False,server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at",sa.DateTime(timezone=True),nullable=False),
        sa.UniqueConstraint("target_type","target_id","concept_key",name="uq_ontology_mapping"))
    op.create_index("ix_ontology_mapping_target","ontology_mappings",["target_type","target_id"])
    op.create_index("ix_ontology_mapping_concept","ontology_mappings",["concept_key"])


def downgrade()->None:
    op.drop_table("ontology_mappings")
    op.drop_table("ontology_relationships")
    op.drop_table("ontology_aliases")
    op.drop_table("ontology_concepts")
