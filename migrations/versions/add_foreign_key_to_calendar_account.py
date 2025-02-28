"""add_foreign_key_to_calendar_account

Revision ID: add_foreign_key_to_calendar_account
Revises: create_user_table
Create Date: 2025-02-28 22:08:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_foreign_key_to_calendar_account'
down_revision = 'create_user_table'
branch_labels = None
depends_on = None


def upgrade():
    # Add foreign key constraint to app_user_email in calendar_account
    with op.batch_alter_table('calendar_account') as batch_op:
        batch_op.create_foreign_key(
            'fk_calendar_account_app_user_email',
            'user',
            ['app_user_email'],
            ['app_user_email']
        )


def downgrade():
    # Remove foreign key constraint
    with op.batch_alter_table('calendar_account') as batch_op:
        batch_op.drop_constraint('fk_calendar_account_app_user_email', type_='foreignkey')