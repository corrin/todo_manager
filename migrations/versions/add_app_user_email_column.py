"""add app_user_email column

Revision ID: add_app_user_email_column
Revises: rename_email_to_calendar_email
Create Date: 2025-02-28 08:21:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_app_user_email_column'
down_revision = 'rename_email_to_calendar_email'
branch_labels = None
depends_on = None


def upgrade():
    # Add app_user_email column as nullable first
    with op.batch_alter_table('calendar_account') as batch_op:
        batch_op.add_column(sa.Column('app_user_email', sa.String(length=120), nullable=True))
    
    # Set all existing records to lakeland@gmail.com
    op.execute("UPDATE calendar_account SET app_user_email = 'lakeland@gmail.com'")
    
    # Now make it non-nullable
    with op.batch_alter_table('calendar_account') as batch_op:
        batch_op.alter_column('app_user_email',
                            existing_type=sa.String(length=120),
                            nullable=False)


def downgrade():
    with op.batch_alter_table('calendar_account') as batch_op:
        batch_op.drop_column('app_user_email') 