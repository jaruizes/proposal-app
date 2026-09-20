"""knowledge document lifecycle and versioning

Revision ID: 0007_knowledge_lifecycle
Revises: 0006_ontology
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision="0007_knowledge_lifecycle"
down_revision="0006_ontology"
branch_labels=None
depends_on=None

def upgrade()->None:
    op.add_column("knowledge_documents",sa.Column("family_id",postgresql.UUID(as_uuid=True),nullable=True))
    op.add_column("knowledge_documents",sa.Column("version",sa.Integer(),nullable=False,server_default="1"))
    op.add_column("knowledge_documents",sa.Column("previous_version_id",postgresql.UUID(as_uuid=True),nullable=True))
    op.execute("UPDATE knowledge_documents SET family_id=id WHERE family_id IS NULL")
    op.alter_column("knowledge_documents","family_id",nullable=False)
    op.create_foreign_key("fk_knowledge_documents_previous_version","knowledge_documents","knowledge_documents",["previous_version_id"],["id"],ondelete="SET NULL")
    op.create_index("ix_knowledge_documents_family_id","knowledge_documents",["family_id"])
    op.create_index("ix_knowledge_documents_family_version","knowledge_documents",["family_id","version"],unique=True)

def downgrade()->None:
    op.drop_index("ix_knowledge_documents_family_version",table_name="knowledge_documents")
    op.drop_index("ix_knowledge_documents_family_id",table_name="knowledge_documents")
    op.drop_constraint("fk_knowledge_documents_previous_version","knowledge_documents",type_="foreignkey")
    op.drop_column("knowledge_documents","previous_version_id")
    op.drop_column("knowledge_documents","version")
    op.drop_column("knowledge_documents","family_id")
