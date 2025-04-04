"""create_user_table

Revision ID: create_user_table
Revises: d661bc6e8631
Create Date: 2025-02-28 22:06:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'create_user_table'
down_revision = 'd661bc6e8631'
branch_labels = None
depends_on = None


def upgrade():
    # Create user table
    op.create_table('user',
        sa.Column('app_login', sa.String(120), nullable=False),
        sa.PrimaryKeyConstraint('app_login')
    )
    
    # Populate user table with existing app_logins from calendar_account
    op.execute("""
        INSERT INTO user (app_login)
        SELECT DISTINCT app_login
        FROM calendar_account
    """)


def downgrade():
    # Drop user table
    op.drop_table('user')