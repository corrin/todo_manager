"""Initial migration based on current models

Revision ID: d8e786a944dd
Revises: 
Create Date: 2025-04-04 19:55:03.282534

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd8e786a944dd'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('tasks',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('app_login', sa.String(length=255), nullable=False),
    sa.Column('task_user_email', sa.String(length=255), nullable=True),
    sa.Column('provider', sa.String(length=50), nullable=False),
    sa.Column('provider_task_id', sa.String(length=255), nullable=False),
    sa.Column('title', sa.String(length=500), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('status', sa.String(length=50), nullable=False),
    sa.Column('due_date', sa.DateTime(), nullable=True),
    sa.Column('priority', sa.Integer(), nullable=True),
    sa.Column('project_id', sa.String(length=255), nullable=True),
    sa.Column('project_name', sa.String(length=255), nullable=True),
    sa.Column('parent_id', sa.String(length=255), nullable=True),
    sa.Column('section_id', sa.String(length=255), nullable=True),
    sa.Column('list_type', sa.String(length=50), nullable=True),
    sa.Column('position', sa.Integer(), nullable=True),
    sa.Column('content_hash', sa.String(length=64), nullable=False),
    sa.Column('last_synced', sa.DateTime(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('app_login', 'provider', 'provider_task_id', name='uq_app_login_provider_task')
    )
    with op.batch_alter_table('tasks', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_tasks_app_login'), ['app_login'], unique=False)
        batch_op.create_index(batch_op.f('ix_tasks_task_user_email'), ['task_user_email'], unique=False)

    op.create_table('user',
    sa.Column('app_login', sa.String(length=120), nullable=False),
    sa.PrimaryKeyConstraint('app_login')
    )
    op.create_table('calendar_account',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('calendar_email', sa.String(length=255), nullable=False),
    sa.Column('app_login', sa.String(length=255), nullable=False),
    sa.Column('provider', sa.String(length=50), nullable=False),
    sa.Column('token', sa.Text(), nullable=False),
    sa.Column('refresh_token', sa.Text(), nullable=True),
    sa.Column('token_uri', sa.String(length=255), nullable=True),
    sa.Column('client_id', sa.String(length=255), nullable=True),
    sa.Column('client_secret', sa.String(length=255), nullable=True),
    sa.Column('scopes', sa.Text(), nullable=True),
    sa.Column('is_primary', sa.Boolean(), nullable=True),
    sa.Column('last_sync', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('needs_reauth', sa.Boolean(), nullable=False),
    sa.ForeignKeyConstraint(['app_login'], ['user.app_login'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('app_login', 'calendar_email', 'provider', name='uq_calendar_account_app_login_provider')
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('calendar_account')
    op.drop_table('user')
    with op.batch_alter_table('tasks', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_tasks_task_user_email'))
        batch_op.drop_index(batch_op.f('ix_tasks_app_login'))

    op.drop_table('tasks')
    # ### end Alembic commands ###
