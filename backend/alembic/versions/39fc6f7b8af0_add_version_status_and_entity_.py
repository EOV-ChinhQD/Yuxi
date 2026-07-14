"""Add version status and entity resolution fields

Revision ID: 39fc6f7b8af0
Revises: 96d0b2c39695
Create Date: 2026-07-14 16:37:52.704913

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '39fc6f7b8af0'
down_revision: Union[str, Sequence[str], None] = '96d0b2c39695'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('knowledge_chunks', sa.Column('chunk_version', sa.String(length=64), nullable=True))
    op.add_column('knowledge_chunks', sa.Column('status', sa.String(length=32), nullable=False, server_default='pending'))
    op.add_column('knowledge_chunks', sa.Column('heading_path', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=True))
    op.add_column('knowledge_chunks', sa.Column('section_type', sa.String(length=64), nullable=True))
    op.create_index(op.f('ix_knowledge_chunks_status'), 'knowledge_chunks', ['status'], unique=False)
    op.add_column('knowledge_graph_entities', sa.Column('canonical_name', sa.String(length=512), nullable=True))
    op.add_column('knowledge_graph_entities', sa.Column('aliases', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=True))
    op.add_column('knowledge_graph_events', sa.Column('event_version', sa.String(length=64), nullable=True))
    op.add_column('knowledge_graph_events', sa.Column('status', sa.String(length=32), nullable=False, server_default='pending'))
    op.add_column('knowledge_graph_events', sa.Column('confidence', sa.Float(), nullable=False, server_default='1.0'))
    op.add_column('knowledge_graph_events', sa.Column('importance', sa.String(length=16), nullable=False, server_default='normal'))
    op.add_column('knowledge_graph_events', sa.Column('event_type', sa.String(length=64), nullable=True))
    op.add_column('knowledge_graph_events', sa.Column('temporal_info', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=True))
    op.add_column('knowledge_graph_events', sa.Column('event_embedding', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=True))
    op.create_index(op.f('ix_knowledge_graph_events_status'), 'knowledge_graph_events', ['status'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_knowledge_graph_events_status'), table_name='knowledge_graph_events')
    op.drop_column('knowledge_graph_events', 'event_embedding')
    op.drop_column('knowledge_graph_events', 'temporal_info')
    op.drop_column('knowledge_graph_events', 'event_type')
    op.drop_column('knowledge_graph_events', 'importance')
    op.drop_column('knowledge_graph_events', 'confidence')
    op.drop_column('knowledge_graph_events', 'status')
    op.drop_column('knowledge_graph_events', 'event_version')
    op.drop_column('knowledge_graph_entities', 'aliases')
    op.drop_column('knowledge_graph_entities', 'canonical_name')
    op.drop_index(op.f('ix_knowledge_chunks_status'), table_name='knowledge_chunks')
    op.drop_column('knowledge_chunks', 'section_type')
    op.drop_column('knowledge_chunks', 'heading_path')
    op.drop_column('knowledge_chunks', 'status')
    op.drop_column('knowledge_chunks', 'chunk_version')
