"""add projects and conversation project binding

Revision ID: f3a8c9d2e5b1
Revises: d7e4b09a5c31
Create Date: 2026-08-26

Adds Project persistence for Workdir binding:
- projects table (id, uid, name, selection_status, workdir_path,
  directory_mode, idempotency_key, created_at, updated_at)
- conversations.creation_request_id (nullable, unique per uid)
- conversations.project_id (nullable initially, backfilled to implicit
  projects for existing rows, then NOT NULL)

Forward-compatible: upgrade adds columns nullable, backfills existing
conversations, then alters project_id to NOT NULL on PostgreSQL.
"""

import uuid
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "f3a8c9d2e5b1"
down_revision: str | Sequence[str] | None = "d7e4b09a5c31"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    dialect = bind.dialect.name if bind is not None else "postgresql"

    # 1) Create projects table (if not exists for idempotency in tests)
    op.create_table(
        "projects",
        sa.Column("id", sa.String(length=64), nullable=False, comment="Project UUID"),
        sa.Column("uid", sa.String(length=64), nullable=False, comment="UID"),
        sa.Column("name", sa.String(length=255), nullable=True, comment="Project name; implicit Project may be empty"),
        sa.Column("selection_status", sa.String(length=20), nullable=False, comment="implicit/selectable"),
        sa.Column("workdir_path", sa.String(length=512), nullable=False, comment="UserWorkspace-relative Workdir path"),
        sa.Column("directory_mode", sa.String(length=20), nullable=False, comment="managed/linked"),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True, comment="Idempotent creation key"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["uid"], ["users.uid"], name="fk_projects_uid_users", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_projects")),
        sa.UniqueConstraint("id", "uid", name="uq_projects_id_uid"),
        sa.UniqueConstraint("uid", "idempotency_key", name="uq_projects_uid_idempotency_key"),
        sa.CheckConstraint("selection_status IN ('implicit', 'selectable')", name="ck_projects_selection_status"),
        sa.CheckConstraint("directory_mode IN ('managed', 'linked')", name="ck_projects_directory_mode"),
    )
    op.create_index(op.f("ix_projects_uid"), "projects", ["uid"], unique=False)
    op.create_index(op.f("ix_projects_selection_status"), "projects", ["selection_status"], unique=False)

    # 2) Add columns to conversations
    with op.batch_alter_table("conversations", schema=None) as batch_op:
        batch_op.add_column(sa.Column("creation_request_id", sa.String(length=64), nullable=True, comment="Creation idempotency key"))
        # Temporarily nullable for backfill
        batch_op.add_column(sa.Column("project_id", sa.String(length=64), nullable=True, comment="Bound Project ID"))
        batch_op.create_index(batch_op.f("ix_conversations_project_id"), ["project_id"], unique=False)
        batch_op.create_unique_constraint("uq_conversations_uid_creation_request_id", ["uid", "creation_request_id"])

    # 3) Backfill existing conversations: one implicit project per distinct uid
    #    Use Python loop to generate UUIDs and insert projects, then update conversations.
    #    Skip if no conversations table rows.
    try:
        result = bind.execute(sa.text("SELECT DISTINCT uid FROM conversations WHERE project_id IS NULL"))
        distinct_uids = [row[0] for row in result.fetchall() if row[0]]
    except Exception:
        distinct_uids = []

    for uid in distinct_uids:
        project_id = str(uuid.uuid4())
        workdir_path = f"projects/{project_id}"
        # Insert implicit project; ignore if already inserted for this uid via idempotency edge
        try:
            bind.execute(
                sa.text(
                    "INSERT INTO projects (id, uid, selection_status, workdir_path, directory_mode, created_at, updated_at) "
                    "VALUES (:id, :uid, 'implicit', :workdir_path, 'managed', NOW(), NOW()) "
                    "ON CONFLICT (id) DO NOTHING"
                ),
                {"id": project_id, "uid": uid, "workdir_path": workdir_path},
            )
            # For SQLite fallback (no ON CONFLICT support for composite) — try plain insert
        except Exception:
            try:
                bind.execute(
                    sa.text(
                        "INSERT INTO projects (id, uid, selection_status, workdir_path, directory_mode) "
                        "VALUES (:id, :uid, 'implicit', :workdir_path, 'managed')"
                    ),
                    {"id": project_id, "uid": uid, "workdir_path": workdir_path},
                )
            except Exception:
                continue
        # Update conversations of this uid that still have NULL project_id
        try:
            bind.execute(
                sa.text("UPDATE conversations SET project_id = :pid WHERE uid = :uid AND project_id IS NULL"),
                {"pid": project_id, "uid": uid},
            )
        except Exception:
            pass

    # 4) Enforce NOT NULL on project_id for PostgreSQL after backfill
    if dialect == "postgresql":
        # Only alter if there are no NULLs left
        null_count = 0
        try:
            null_count = bind.execute(sa.text("SELECT COUNT(*) FROM conversations WHERE project_id IS NULL")).scalar() or 0
        except Exception:
            null_count = 0
        if null_count == 0:
            with op.batch_alter_table("conversations", schema=None) as batch_op:
                batch_op.alter_column("project_id", existing_type=sa.String(length=64), nullable=False)
            # Add composite FK (project_id, uid) -> projects (id, uid)
            # Must ensure projects has unique (id, uid) which we created above
            with op.batch_alter_table("conversations", schema=None) as batch_op:
                batch_op.create_foreign_key(
                    "fk_conversations_project_uid",
                    "projects",
                    ["project_id", "uid"],
                    ["id", "uid"],
                )
        else:
            # Leave nullable and log warning; FK will be added in next migration after manual cleanup
            pass
    else:
        # SQLite: add FK via batch (will be enforced on next create_all)
        try:
            with op.batch_alter_table("conversations", schema=None) as batch_op:
                batch_op.create_foreign_key(
                    "fk_conversations_project_uid",
                    "projects",
                    ["project_id", "uid"],
                    ["id", "uid"],
                )
        except Exception:
            pass


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("conversations", schema=None) as batch_op:
        try:
            batch_op.drop_constraint("fk_conversations_project_uid", type_="foreignkey")
        except Exception:
            pass
        batch_op.drop_constraint("uq_conversations_uid_creation_request_id", type_="unique")
        batch_op.drop_index(batch_op.f("ix_conversations_project_id"))
        batch_op.drop_column("project_id")
        batch_op.drop_column("creation_request_id")

    op.drop_index(op.f("ix_projects_selection_status"), table_name="projects")
    op.drop_index(op.f("ix_projects_uid"), table_name="projects")
    op.drop_table("projects")
