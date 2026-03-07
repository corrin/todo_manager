# External Account Refactoring Plan

## Current Situation
- You broke the basic Flask/Alembic setup.  This needs to be corrected back to best pracice before the task is resumed.
- Authentication and token management is currently handled in `CalendarAccount` model
- This functionality is reused across calendar and task providers
- Leads to confusion and potential code duplication
- [ ] Alembic is working correctly
- [x] Added bitfields use_for_calendar and use_for_tasks to ExternalAccount model
- [x] Implemented ExternalAccount model in codebase
- [x] Updated primary account methods to handle both calendar and tasks
- [x] Resolve Alembic migration issues (created migration 5a3b7c8d2f1e)
- [x] Implemented unified account removal endpoint (/database/remove_external_account)
- [x] Removed old calendar-specific removal endpoint (/meetings/remove_calendar_account)
- [ ] Delete CalendarAccount and TaskAccount
- [x] Refactored settings template to unified ExternalAccount view
  - Combined Task and Calendar accounts into single table
  - Shows both capabilities per account (Tasks/Calendar)
  - Maintained all existing functionality
- [ ] Add UI checkboxes for use_for fields (future enhancement)

## Proposed Solution
Create new `ExternalAccount` model to centralize external account management.

### New ExternalAccount Model Structure
```python
class ExternalAccount(db.Model):
    """Model for managing all external service accounts (Google, O365, Todoist)."""
    
    __tablename__ = 'external_account'
    
    id = db.Column(MySQLUUID, primary_key=True, default=uuid.uuid4)
    account_email = db.Column(db.String(255), nullable=False)
    user_id = db.Column(MySQLUUID, db.ForeignKey('user.id'), nullable=False)
    provider = db.Column(db.String(50), nullable=False)  # 'google', 'o365', 'todoist'
    token = db.Column(db.Text, nullable=False)
    refresh_token = db.Column(db.Text)
    token_uri = db.Column(db.String(255))
    client_id = db.Column(db.String(255))
    client_secret = db.Column(db.String(255))
    scopes = db.Column(db.Text)
    use_for_tasks = db.Column(db.Boolean, default=False)
    use_for_calendar = db.Column(db.Boolean, default=False)
    is_primary_calendar = db.Column(db.Boolean, default=False)
    is_primary_tasks = db.Column(db.Boolean, default=False)
    last_sync = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    needs_reauth = db.Column(db.Boolean, nullable=False, default=False)
    
    # Relationships
    user = relationship("User", back_populates="external_accounts")
    
    # Methods to include:
    # - All token management methods from CalendarAccount
    # - Generic account management methods
    # - Provider-specific functionality
```

### Migration Steps
1. Create new ExternalAccount model with all auth-related fields
2. Update CalendarAccount to:
   - Remove auth-related fields
   - Add foreign key to ExternalAccount
   - Consider keeping some fields temporarialy to ease the migration
3. Create data migration to move auth data from CalendarAccount to ExternalAccount
4. Update all task providers to use ExternalAccount
5. Update UI/API endpoints to handle new model structure
6. DELETE CalendarAccount and TaskAccount models

### Benefits
- Clear separation of concerns
- Single source of truth for external accounts
- Easier to add new account types
- Reduced code duplication

### Implementation Timeline
1. [COMPLETED] Design and documentation
2. [COMPLETED] Implement ExternalAccount model and basic CRUD
   - [x] Model structure implemented
   - [x] Primary account methods updated
   - [x] Schema migration created and applied
3. Migrate CalendarAccount functionality
4. Update task providers and UI

## Implementation Notes
- Primary account methods now take an account_type parameter ('calendar' or 'tasks')
- Methods use is_primary_calendar and is_primary_tasks fields
- Removed fallback to first account to maintain data model standards
- Error handling improved with proper exceptions