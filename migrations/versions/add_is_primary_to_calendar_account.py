"""Add is_primary column to calendar_account table

Revision ID: add_is_primary_to_calendar_account
Revises: d661bc6e8631
Create Date: 2025-02-28 23:04:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_is_primary_to_calendar_account'
down_revision = '53b5220d3727'
branch_labels = None
depends_on = None


def upgrade():
    # Add is_primary column with default value of False
    op.add_column('calendar_account', sa.Column('is_primary', sa.Boolean(), nullable=True, server_default='0'))
    
    # Set the first account for each user as primary
    conn = op.get_bind()
    conn.execute("""
        WITH RankedAccounts AS (
            SELECT 
                id,
                app_user_email,
                ROW_NUMBER() OVER (PARTITION BY app_user_email ORDER BY created_at) as rn
            FROM calendar_account
        )
        UPDATE calendar_account
        SET is_primary = 1
        WHERE id IN (
            SELECT id FROM RankedAccounts WHERE rn = 1
        )
    """)
    
    # Make the column non-nullable after setting initial values
    op.alter_column('calendar_account', 'is_primary', nullable=False, server_default=None)


def downgrade():
    op.drop_column('calendar_account', 'is_primary')