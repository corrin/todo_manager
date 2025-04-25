"""create_external_account_and_refactor_calendar_account

Revision ID: 5a3b7c8d2f1e
Revises: 460449018edf
Create Date: 2025-04-26 07:40:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = '5a3b7c8d2f1e'
down_revision = '460449018edf'
branch_labels = None
depends_on = None


def upgrade():
    # Create ExternalAccount table
    op.create_table('external_account',
        sa.Column('id', mysql.CHAR(36), nullable=False),
        sa.Column('provider', sa.String(length=50), nullable=False),
        sa.Column('token', sa.Text(), nullable=False),
        sa.Column('refresh_token', sa.Text(), nullable=True),
        sa.Column('token_uri', sa.String(length=255), nullable=True),
        sa.Column('client_id', sa.String(length=255), nullable=True),
        sa.Column('client_secret', sa.String(length=255), nullable=True),
        sa.Column('scopes', sa.Text(), nullable=True),
        sa.Column('needs_reauth', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    # Add external_account_id to calendar_account
    op.add_column('calendar_account', 
        sa.Column('external_account_id', mysql.CHAR(36), nullable=True))
    op.create_foreign_key(
        'fk_calendar_account_external_account',
        'calendar_account', 'external_account',
        ['external_account_id'], ['id']
    )

    # Data migration will be handled in a separate step


def downgrade():
    # Drop foreign key first
    op.drop_constraint('fk_calendar_account_external_account', 'calendar_account', type_='foreignkey')
    
    # Remove external_account_id column
    op.drop_column('calendar_account', 'external_account_id')
    
    # Drop external_account table
    op.drop_table('external_account')