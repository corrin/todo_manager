"""Migration to fix calendar_account unique constraint."""

from alembic import op

def upgrade():
    # Drop existing constraint
    op.drop_constraint('uq_calendar_account_email_provider', 'calendar_account')
    
    # Add new constraint including app_user_email
    op.create_unique_constraint(
        'uq_calendar_account_user_email_provider',
        'calendar_account',
        ['app_user_email', 'calendar_email', 'provider']
    )

def downgrade():
    # Drop new constraint
    op.drop_constraint('uq_calendar_account_user_email_provider', 'calendar_account')
    
    # Restore original constraint
    op.create_unique_constraint(
        'uq_calendar_account_email_provider',
        'calendar_account',
        ['calendar_email', 'provider']
    ) 