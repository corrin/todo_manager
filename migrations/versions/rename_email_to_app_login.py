"""Rename email-related user identifiers to app_login

Revision ID: rename_email_to_login
Revises: 4ff2bff41a0d
Create Date: 2025-04-04 18:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'rename_email_to_app_login'
down_revision = '4ff2bff41a0d'
branch_labels = None
depends_on = None


def upgrade():
    # Rename app_user_email to app_login in User model
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.alter_column('app_user_email',
                              new_column_name='app_login',
                              existing_type=sa.String(length=120),
                              nullable=False)

    # Update foreign key in CalendarAccount model
    with op.batch_alter_table('calendar_account', schema=None) as batch_op:
        # Drop the existing foreign key constraint
        batch_op.drop_constraint('fk_calendar_account_app_user_email', type_='foreignkey')
        # Drop the existing unique constraint
        batch_op.drop_constraint('uq_calendar_account_user_email_provider', type_='unique')
        # Rename app_user_email to app_login
        batch_op.alter_column('app_user_email',
                              new_column_name='app_login',
                              existing_type=sa.String(length=255),
                              nullable=False)
        # Create new foreign key constraint
        batch_op.create_foreign_key(
            'fk_calendar_account_app_login',
            'user',
            ['app_login'],
            ['app_login']
        )
        # Create new unique constraint
        batch_op.create_unique_constraint(
            'uq_calendar_account_app_login_provider',
            ['app_login', 'calendar_email', 'provider']
        )

    # Rename user_email to app_login in Task model
    with op.batch_alter_table('tasks', schema=None) as batch_op:
        # Drop the existing index
        batch_op.drop_index('ix_tasks_user_email')
        # Drop the existing unique constraint
        batch_op.drop_constraint('uq_user_provider_task', type_='unique')
        # Rename user_email to login
        batch_op.alter_column('user_email',
                              new_column_name='app_login',
                              existing_type=sa.String(length=255),
                              nullable=False)
        # Create new index
        batch_op.create_index(
            'ix_tasks_app_login',
            ['app_login'],
            unique=False
        )
        # Create new unique constraint
        batch_op.create_unique_constraint(
            'uq_app_login_provider_task',
            ['app_login', 'provider', 'provider_task_id']
        )


def downgrade():
    # Revert changes in Task model
    with op.batch_alter_table('tasks', schema=None) as batch_op:
        # Drop the new index
        batch_op.drop_index('ix_tasks_app_login')
        # Drop the new unique constraint
        batch_op.drop_constraint('uq_app_login_provider_task', type_='unique')
        # Rename app_login back to user_email
        batch_op.alter_column('app_login',
                              new_column_name='user_email',
                              existing_type=sa.String(length=255),
                              nullable=False)
        # Recreate the original index
        batch_op.create_index(
            'ix_tasks_user_email',
            ['user_email'],
            unique=False
        )
        # Recreate the original unique constraint
        batch_op.create_unique_constraint(
            'uq_user_provider_task',
            ['user_email', 'provider', 'provider_task_id']
        )

    # Revert changes in CalendarAccount model
    with op.batch_alter_table('calendar_account', schema=None) as batch_op:
        # Drop the new foreign key constraint
        batch_op.drop_constraint('fk_calendar_account_app_login', type_='foreignkey')
        # Drop the new unique constraint
        batch_op.drop_constraint('uq_calendar_account_app_login_provider', type_='unique')
        # Rename app_login back to app_user_email
        batch_op.alter_column('app_login',
                              new_column_name='app_user_email',
                              existing_type=sa.String(length=255),
                              nullable=False)
        # Recreate the original foreign key constraint
        batch_op.create_foreign_key(
            'fk_calendar_account_app_user_email',
            'user',
            ['app_user_email'],
            ['app_user_email']
        )
        # Recreate the original unique constraint
        batch_op.create_unique_constraint(
            'uq_calendar_account_user_email_provider',
            ['app_user_email', 'calendar_email', 'provider']
        )

    # Revert changes in User model
    with op.batch_alter_table('user', schema=None) as batch_op:
        # Rename app_login back to app_user_email
        batch_op.alter_column('app_login',
                              new_column_name='app_user_email',
                              existing_type=sa.String(length=120),
                              nullable=False)