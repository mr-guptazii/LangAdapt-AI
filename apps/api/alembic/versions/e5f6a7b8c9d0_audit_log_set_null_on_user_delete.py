"""audit_logs.actor_user_id and users.teacher_id: ON DELETE SET NULL

Real account deletion (app/api/v1/settings.py delete_account) hard-deletes
the User row so it cascades to every owned learner-data row. Without this
change, that delete would fail outright: both FKs had no ON DELETE behavior
(default RESTRICT) — any account that had ever logged in, reset a password,
or done anything else audit-logged could never be deleted, and once
teacher_id is wired up (currently unused), a teacher's account would become
undeletable while any student still referenced them. The audit row itself is
kept — only the actor reference is cleared — so "an account existed and did
X" remains auditable without retaining a live reference to a deleted account.

Does not need the 'vector' extension.

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-08-16 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("audit_logs_actor_user_id_fkey", "audit_logs", type_="foreignkey")
    op.create_foreign_key(
        "audit_logs_actor_user_id_fkey", "audit_logs", "users",
        ["actor_user_id"], ["id"], ondelete="SET NULL",
    )
    op.drop_constraint("users_teacher_id_fkey", "users", type_="foreignkey")
    op.create_foreign_key(
        "users_teacher_id_fkey", "users", "users",
        ["teacher_id"], ["id"], ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("users_teacher_id_fkey", "users", type_="foreignkey")
    op.create_foreign_key(
        "users_teacher_id_fkey", "users", "users",
        ["teacher_id"], ["id"],
    )
    op.drop_constraint("audit_logs_actor_user_id_fkey", "audit_logs", type_="foreignkey")
    op.create_foreign_key(
        "audit_logs_actor_user_id_fkey", "audit_logs", "users",
        ["actor_user_id"], ["id"],
    )
