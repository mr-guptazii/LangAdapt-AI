"""widen agent_decisions.recommended_action

agent_decisions.recommended_action was VARCHAR(128), far too narrow for the
free-text sentence adaptation_agent actually generates (AdaptationDecision.
recommended_action has no length limit at the LLM-output layer until this
same change — see app/schemas/agent_io.py). A longer-than-128-char value
crashed persist_learning_event outright in production with
asyncpg.exceptions.StringDataRightTruncationError, an unhandled 500 on the
whole chat turn — reproduced live against the real production database via
Render's shell. Widens the column to match reason_summary's existing 500,
which already holds comparable prose content on the same table.

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-08-17 22:15:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("agent_decisions", "recommended_action", type_=sa.String(500), existing_type=sa.String(128))


def downgrade() -> None:
    # Not reversible if any existing row's recommended_action is now >128 chars
    # (which is exactly the scenario this migration exists to allow) — truncate
    # defensively rather than fail the downgrade outright.
    op.execute("UPDATE agent_decisions SET recommended_action = LEFT(recommended_action, 128) WHERE LENGTH(recommended_action) > 128")
    op.alter_column("agent_decisions", "recommended_action", type_=sa.String(128), existing_type=sa.String(500))
