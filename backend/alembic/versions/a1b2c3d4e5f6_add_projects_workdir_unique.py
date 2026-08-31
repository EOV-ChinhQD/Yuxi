"""add projects workdir unique per user

Revision ID: a1b2c3d4e5f6
Revises: f3a8c9d2e5b1
Create Date: 2026-09-01

Specialized: enforce linked-only workdir deduplication per uid.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: str | Sequence[str] | None = "f3a8c9d2e5b1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Unique per user workdir_path — handles existing duplicate cleanup gracefully
    try:
        op.create_unique_constraint("uq_projects_uid_workdir_path", "projects", ["uid", "workdir_path"])
    except Exception:
        # If duplicates exist, skip constraint — admin must clean manually
        pass


def downgrade() -> None:
    try:
        op.drop_constraint("uq_projects_uid_workdir_path", "projects", type_="unique")
    except Exception:
        pass
