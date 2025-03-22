"""Add Task model and remove TaskOrder

Revision ID: 4ff2bff41a0d
Revises: add_needs_reauth
Create Date: 2025-03-22 19:36:19.028637

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4ff2bff41a0d'
down_revision = 'add_needs_reauth'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('tasks',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_email', sa.String(length=255), nullable=False),
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
    sa.UniqueConstraint('user_email', 'provider', 'provider_task_id', name='uq_user_provider_task')
    )
    with op.batch_alter_table('tasks', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_tasks_user_email'), ['user_email'], unique=False)

    op.drop_table('_alembic_tmp_calendar_account')
    with op.batch_alter_table('calendar_account', schema=None) as batch_op:
        batch_op.alter_column('calendar_email',
               existing_type=sa.VARCHAR(length=120),
               type_=sa.String(length=255),
               existing_nullable=False)
        batch_op.alter_column('app_user_email',
               existing_type=sa.VARCHAR(length=120),
               type_=sa.String(length=255),
               existing_nullable=False)
        batch_op.alter_column('token_uri',
               existing_type=sa.VARCHAR(length=200),
               type_=sa.String(length=255),
               existing_nullable=True)
        batch_op.alter_column('client_id',
               existing_type=sa.VARCHAR(length=200),
               type_=sa.String(length=255),
               existing_nullable=True)
        batch_op.alter_column('client_secret',
               existing_type=sa.VARCHAR(length=200),
               type_=sa.String(length=255),
               existing_nullable=True)
        batch_op.drop_constraint('_calendar_email_provider_app_user_email_uc', type_='unique')
        batch_op.create_unique_constraint('uq_calendar_account_user_email_provider', ['app_user_email', 'calendar_email', 'provider'])

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('calendar_account', schema=None) as batch_op:
        batch_op.drop_constraint('uq_calendar_account_user_email_provider', type_='unique')
        batch_op.create_unique_constraint('_calendar_email_provider_app_user_email_uc', ['calendar_email', 'provider', 'app_user_email'])
        batch_op.alter_column('client_secret',
               existing_type=sa.String(length=255),
               type_=sa.VARCHAR(length=200),
               existing_nullable=True)
        batch_op.alter_column('client_id',
               existing_type=sa.String(length=255),
               type_=sa.VARCHAR(length=200),
               existing_nullable=True)
        batch_op.alter_column('token_uri',
               existing_type=sa.String(length=255),
               type_=sa.VARCHAR(length=200),
               existing_nullable=True)
        batch_op.alter_column('app_user_email',
               existing_type=sa.String(length=255),
               type_=sa.VARCHAR(length=120),
               existing_nullable=False)
        batch_op.alter_column('calendar_email',
               existing_type=sa.String(length=255),
               type_=sa.VARCHAR(length=120),
               existing_nullable=False)

    op.create_table('_alembic_tmp_calendar_account',
    sa.Column('id', sa.INTEGER(), nullable=False),
    sa.Column('calendar_email', sa.VARCHAR(length=255), nullable=False),
    sa.Column('provider', sa.VARCHAR(length=50), nullable=False),
    sa.Column('token', sa.TEXT(), nullable=False),
    sa.Column('refresh_token', sa.TEXT(), nullable=True),
    sa.Column('token_uri', sa.VARCHAR(length=255), nullable=True),
    sa.Column('client_id', sa.VARCHAR(length=255), nullable=True),
    sa.Column('client_secret', sa.VARCHAR(length=255), nullable=True),
    sa.Column('scopes', sa.TEXT(), nullable=True),
    sa.Column('last_sync', sa.DATETIME(), nullable=True),
    sa.Column('created_at', sa.DATETIME(), nullable=True),
    sa.Column('app_user_email', sa.VARCHAR(length=255), nullable=False),
    sa.Column('is_primary', sa.BOOLEAN(), server_default=sa.text("'0'"), nullable=True),
    sa.Column('needs_reauth', sa.BOOLEAN(), nullable=False),
    sa.ForeignKeyConstraint(['app_user_email'], ['user.app_user_email'], name='fk_calendar_account_app_user_email'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('app_user_email', 'calendar_email', 'provider', name='uq_calendar_account_user_email_provider')
    )
    with op.batch_alter_table('tasks', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_tasks_user_email'))

    op.drop_table('tasks')
    # ### end Alembic commands ###
