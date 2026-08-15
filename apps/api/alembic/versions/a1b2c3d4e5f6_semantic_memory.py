"""semantic memory (pgvector)

Isolated from the initial schema migration on purpose: this is the one migration
that requires the postgres 'vector' extension (pgvector) to be installed on the
database server. The bundled docker-compose.yml uses the `pgvector/pgvector`
Postgres image, where this works out of the box. On a bare-metal Postgres install
(e.g. native Windows/Linux packages) you must install the pgvector extension
first — see https://github.com/pgvector/pgvector#installation — before running
this migration; every other migration has no such dependency.

Revision ID: a1b2c3d4e5f6
Revises: 168d079a7f17
Create Date: 2026-08-15 19:30:00.000000

"""
from typing import Sequence, Union

import pgvector.sqlalchemy
import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "168d079a7f17"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "semantic_memories",
        sa.Column("learner_profile_id", sa.UUID(), nullable=False),
        sa.Column("learner_memory_id", sa.UUID(), nullable=True),
        sa.Column("text", sa.String(length=1000), nullable=False),
        sa.Column("embedding", pgvector.sqlalchemy.vector.VECTOR(dim=384), nullable=False),
        sa.Column("meta", sa.JSON(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["learner_memory_id"], ["learner_memories.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["learner_profile_id"], ["learner_profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_semantic_memories_learner_profile_id"), "semantic_memories", ["learner_profile_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_semantic_memories_learner_profile_id"), table_name="semantic_memories")
    op.drop_table("semantic_memories")
    # Extension is intentionally left installed on downgrade — other databases /
    # schemas on the same server may depend on it.
