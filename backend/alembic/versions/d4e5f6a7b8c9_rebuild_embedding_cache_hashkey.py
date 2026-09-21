"""rebuild embedding_cache on hash_key schema

Revision ID: d4e5f6a7b8c9
Revises: b2c263690c44
Create Date: 2026-09-21

The b2c263690c44 migration created embedding_cache(cache_key, file_id, ...)
but yuxi.core.embedding_cache queries embedding_cache(hash_key, embedding)
via raw SQL, and models_knowledge keeps a single EmbeddingCacheModel with
__tablename__ = "embedding_cache". The stale Column-style EmbeddingCache
class sharing the same table name crashed SQLAlchemy metadata at import.
This migration rebuilds the (always-empty-in-practice) table on the schema
the code actually uses.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, Sequence[str], None] = 'b2c263690c44'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_table('embedding_cache')
    op.create_table(
        'embedding_cache',
        sa.Column('hash_key', sa.String(length=64), nullable=False),
        sa.Column('embedding', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('hash_key'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('embedding_cache')
