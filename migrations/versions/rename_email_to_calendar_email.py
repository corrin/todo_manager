"""rename email to calendar_email

Revision ID: rename_email_to_calendar_email
Revises: 97bcd9b1ee24
Create Date: 2025-02-28 08:17:25.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector


# revision identifiers, used by Alembic.
revision = 'rename_email_to_calendar_email'
down_revision = '97bcd9b1ee24'  # Updated to point to the existing migration
branch_labels = None
depends_on = None


def upgrade():
    # Get the database connection
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    
    # Check if the old column exists before trying to rename it
    columns = [col['name'] for col in inspector.get_columns('calendar_account')]
    if 'email' in columns and 'calendar_email' not in columns:
        with op.batch_alter_table('calendar_account') as batch_op:
            batch_op.alter_column('email',
                                new_column_name='calendar_email',
                                existing_type=sa.String(length=120),
                                existing_nullable=False)


def downgrade():
    # Get the database connection
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    
    # Check if the new column exists before trying to rename it back
    columns = [col['name'] for col in inspector.get_columns('calendar_account')]
    if 'calendar_email' in columns and 'email' not in columns:
        with op.batch_alter_table('calendar_account') as batch_op:
            batch_op.alter_column('calendar_email',
                                new_column_name='email',
                                existing_type=sa.String(length=120),
                                existing_nullable=False) 