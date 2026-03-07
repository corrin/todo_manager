"""Rename openai_key to ai_api_key and drop ai_provider

Revision ID: afa448aca65a
Revises: 1f3226b41e1b
Create Date: 2026-03-07 21:21:16.993073

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'afa448aca65a'
down_revision = '1f3226b41e1b'
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column('app_user', 'openai_key', new_column_name='ai_api_key', existing_type=sa.Text())
    op.drop_column('app_user', 'ai_provider')


def downgrade():
    op.alter_column('app_user', 'ai_api_key', new_column_name='openai_key', existing_type=sa.Text())
    op.add_column('app_user', sa.Column('ai_provider', sa.String(length=50), nullable=True))
