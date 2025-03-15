"""add needs_reauth column

Revision ID: add_needs_reauth
Revises: add_is_primary_to_calendar_account
"""
from alembic import op
import sqlalchemy as sa

revision = 'add_needs_reauth'
down_revision = 'add_is_primary_to_calendar_account'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('calendar_account', sa.Column('needs_reauth', sa.Boolean(), nullable=False, server_default='0'))

def downgrade():
    op.drop_column('calendar_account', 'needs_reauth') 