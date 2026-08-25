"""add_agent_run_requests_and_config_options

Bổ sung 2 bảng phục vụ tính năng port từ auth/Yuxi:
- agent_run_requests: hàng đợi yêu cầu FIFO theo thread của agent (idempotent bằng request_id)
- config_options: cấu hình dùng chung do code định nghĩa và admin bảo trì giá trị (OCR là consumer đầu tiên)

Revision ID: d7e4b09a5c31
Revises: b2c263690c44
Create Date: 2026-08-25

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'd7e4b09a5c31'
down_revision: Union[str, Sequence[str], None] = 'b2c263690c44'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

JSON_VARIANT = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql')


def upgrade() -> None:
    """Upgrade schema."""
    # Bảng hàng đợi yêu cầu run của agent; input_message/dispatched_run tham chiếu bảng đã có sẵn
    op.create_table('agent_run_requests',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False, comment='Primary key'),
        sa.Column('request_id', sa.String(length=64), nullable=False, comment='Idempotency request ID'),
        sa.Column('uid', sa.String(length=64), nullable=False, comment='UID'),
        sa.Column('agent_slug', sa.String(length=64), nullable=False, comment='Agent slug'),
        sa.Column('conversation_thread_id', sa.String(length=64), nullable=False, comment='Conversation thread ID'),
        sa.Column('source', sa.String(length=32), nullable=False, server_default='chat', comment='Request source: chat/agent_call/eval'),
        sa.Column('channel', sa.String(length=32), nullable=False, server_default='web', comment='Request channel: web/api/im/internal'),
        sa.Column('external_id', sa.String(length=128), nullable=True, comment='Message or call ID on the source side'),
        sa.Column('origin_metadata', JSON_VARIANT, nullable=False, comment='Source metadata snapshot'),
        sa.Column('queue_policy', sa.String(length=16), nullable=False, server_default='enqueue', comment='Queue policy: enqueue/reject/steer'),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='queued', comment='Request status: queued/dispatched/cancelled/rejected/failed'),
        sa.Column('input_message_id', sa.Integer(), nullable=False, comment='Associated input message ID'),
        sa.Column('dispatched_run_id', sa.String(length=64), nullable=True, comment='Dispatched AgentRun ID'),
        sa.Column('input_payload', JSON_VARIANT, nullable=False, comment='Raw input payload snapshot'),
        sa.Column('error_message', sa.Text(), nullable=True, comment='Error message when rejected/failed'),
        sa.Column('created_at', sa.DateTime(), nullable=False, comment='Creation time'),
        sa.Column('dispatched_at', sa.DateTime(), nullable=True, comment='Dispatch time'),
        sa.Column('updated_at', sa.DateTime(), nullable=False, comment='Update time'),
        sa.ForeignKeyConstraint(['input_message_id'], ['messages.id'], ),
        sa.ForeignKeyConstraint(['dispatched_run_id'], ['agent_runs.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('request_id', name='uq_agent_run_requests_request_id')
    )
    op.create_index(op.f('ix_agent_run_requests_request_id'), 'agent_run_requests', ['request_id'], unique=True)
    op.create_index(op.f('ix_agent_run_requests_external_id'), 'agent_run_requests', ['external_id'], unique=False)
    # Chỉ số phục vụ truy vấn hàng đợi FIFO theo (uid, agent, thread, status, thời gian tạo)
    op.create_index('ix_agent_run_requests_queue',
        'agent_run_requests',
        ['uid', 'agent_slug', 'conversation_thread_id', 'status', 'created_at', 'id'],
        unique=False,
    )

    # Bảng cấu hình hệ thống: key duy nhất, params là schema, value là giá trị admin lưu
    op.create_table('config_options',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('key', sa.String(length=100), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('params', JSON_VARIANT, nullable=False, comment='Schema/tham số của option'),
        sa.Column('value', JSON_VARIANT, nullable=False, comment='Giá trị hiện tại do admin thiết lập'),
        sa.Column('created_by', sa.String(length=100), nullable=True),
        sa.Column('updated_by', sa.String(length=100), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('key', name='uq_config_options_key')
    )
    op.create_index(op.f('ix_config_options_key'), 'config_options', ['key'], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_config_options_key'), table_name='config_options')
    op.drop_table('config_options')
    op.drop_index('ix_agent_run_requests_queue', table_name='agent_run_requests')
    op.drop_index(op.f('ix_agent_run_requests_external_id'), table_name='agent_run_requests')
    op.drop_index(op.f('ix_agent_run_requests_request_id'), table_name='agent_run_requests')
    op.drop_table('agent_run_requests')
