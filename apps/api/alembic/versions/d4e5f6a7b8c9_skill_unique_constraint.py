"""skill unique constraint + dedup

Skill.language_code/code had no DB-level uniqueness constraint (see
app/models/language.py) — nothing ever stopped a re-run of scripts.seed (or a
race between two concurrent runs) from leaving duplicate rows for the same
(language_code, code). Every .scalar_one_or_none() lookup against Skill then
raised MultipleResultsFound, an unhandled exception — reproduced live: this
500'd /practice/next consistently for a real account while every other
endpoint sharing the same learner_profile worked fine (see the app-code fix
in 669d528, which changed those lookups to .scalars().first() as a defensive
stopgap; this migration is the actual source-level fix).

For each duplicate group, keeps the oldest row (MIN(created_at), tie-broken
by id) as the "keeper" and reassigns every foreign key pointing at a "loser"
row to point at the keeper instead, before deleting the losers. skill_mastery
needs special handling: reassigning a loser's skill_id blindly could create a
second mastery row for the same (learner_profile_id, keeper skill_id) pair,
since skill_mastery itself has no uniqueness constraint either (see
app/models/mastery.py) — where a learner already has a mastery row against
the keeper, the loser's row is dropped instead of merged (no reliable way to
combine two partially-progressed mastery/spaced-repetition states without a
product decision on which one should win; dropping the redundant one is safer
than silently overwriting real progress data with a coin flip).

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-08-17 21:30:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TEMP TABLE skill_dedup_map AS
        SELECT s.id AS loser_id, keeper.id AS keeper_id
        FROM skills s
        JOIN (
            SELECT DISTINCT ON (language_code, code) id, language_code, code
            FROM skills
            ORDER BY language_code, code, created_at ASC, id ASC
        ) keeper ON keeper.language_code = s.language_code AND keeper.code = s.code
        WHERE s.id != keeper.id
    """)

    # Simple FK reassignments: no uniqueness constraint at risk on these tables.
    op.execute("""
        UPDATE teaching_strategies SET skill_id = m.keeper_id
        FROM skill_dedup_map m WHERE teaching_strategies.skill_id = m.loser_id
    """)
    op.execute("""
        UPDATE agent_decisions SET target_skill_id = m.keeper_id
        FROM skill_dedup_map m WHERE agent_decisions.target_skill_id = m.loser_id
    """)
    op.execute("""
        UPDATE learner_errors SET skill_id = m.keeper_id
        FROM skill_dedup_map m WHERE learner_errors.skill_id = m.loser_id
    """)
    op.execute("""
        UPDATE learner_memories SET related_skill_id = m.keeper_id
        FROM skill_dedup_map m WHERE learner_memories.related_skill_id = m.loser_id
    """)
    op.execute("""
        UPDATE practice_questions SET skill_id = m.keeper_id
        FROM skill_dedup_map m WHERE practice_questions.skill_id = m.loser_id
    """)
    op.execute("""
        UPDATE practice_questions SET source_skill_id = m.keeper_id
        FROM skill_dedup_map m WHERE practice_questions.source_skill_id = m.loser_id
    """)
    op.execute("""
        UPDATE learning_recommendations SET target_skill_id = m.keeper_id
        FROM skill_dedup_map m WHERE learning_recommendations.target_skill_id = m.loser_id
    """)

    # skill_mastery: drop a loser-pointing row where the same learner already
    # has a mastery row against the keeper skill, then reassign the rest.
    op.execute("""
        DELETE FROM skill_mastery sm
        USING skill_dedup_map m
        WHERE sm.skill_id = m.loser_id
        AND EXISTS (
            SELECT 1 FROM skill_mastery sm2
            WHERE sm2.learner_profile_id = sm.learner_profile_id AND sm2.skill_id = m.keeper_id
        )
    """)
    op.execute("""
        UPDATE skill_mastery sm SET skill_id = m.keeper_id
        FROM skill_dedup_map m WHERE sm.skill_id = m.loser_id
    """)

    op.execute("DELETE FROM skills WHERE id IN (SELECT loser_id FROM skill_dedup_map)")
    op.execute("DROP TABLE skill_dedup_map")

    op.create_unique_constraint("uq_skills_language_code_code", "skills", ["language_code", "code"])


def downgrade() -> None:
    op.drop_constraint("uq_skills_language_code_code", "skills", type_="unique")
    # Deduplication is not reversible — the merged/dropped rows are gone.
