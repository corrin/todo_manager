"""Migration to add needs_reauth column to calendar_account table."""

from alembic import op
import sqlalchemy as sa

def upgrade():
    # Add needs_reauth column with default False
    op.add_column('calendar_account', 
                 sa.Column('needs_reauth', sa.Boolean(), 
                          nullable=False, 
                          server_default=sa.false()))

def downgrade():
    # Remove needs_reauth column
    op.drop_column('calendar_account', 'needs_reauth') 