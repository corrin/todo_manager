"""Update calendar account unique constraint

Revision ID: 53b5220d3727
Revises: add_foreign_key_to_calendar_account
Create Date: 2025-02-28 22:26:52.585523

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '53b5220d3727'
down_revision = 'add_foreign_key_to_calendar_account'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('calendar_account', schema=None) as batch_op:
        batch_op.drop_constraint('_calendar_email_provider_uc', type_='unique')
        batch_op.create_unique_constraint('_calendar_email_provider_app_user_email_uc', ['calendar_email', 'provider', 'app_user_email'])

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('calendar_account', schema=None) as batch_op:
        batch_op.drop_constraint('_calendar_email_provider_app_user_email_uc', type_='unique')
        batch_op.create_unique_constraint('_calendar_email_provider_uc', ['calendar_email', 'provider'])

    # ### end Alembic commands ###
