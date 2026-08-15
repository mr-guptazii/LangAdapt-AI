"""merge heads (semantic_memory + analytics_and_usage)

No-op merge so `alembic upgrade head` resolves to a single target again after
the pgvector-dependent and pgvector-independent branches diverged from
168d079a7f17. Applying this migration on a database that's missing the
'vector' extension still works up through analytics_and_usage — only
semantic_memory itself is blocked, exactly as before this branch existed.

Revision ID: c3d4e5f6a7b8
Revises: a1b2c3d4e5f6, b2c3d4e5f6a7
Create Date: 2026-08-16 10:05:00.000000

"""
from typing import Sequence, Union

revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, tuple[str, ...], None] = ("a1b2c3d4e5f6", "b2c3d4e5f6a7")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
