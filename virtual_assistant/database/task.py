from sqlalchemy import Column, Integer, String, ForeignKey, UniqueConstraint, Text, DateTime
from sqlalchemy.orm import relationship
from virtual_assistant.database.database import db
from virtual_assistant.database.user import MySQLUUID
from datetime import datetime
import hashlib
import json
import uuid
from virtual_assistant.utils.logger import logger

class Task(db.Model):
    """Comprehensive task model that tracks tasks across all providers."""
    __tablename__ = 'tasks'

    # Primary identification
    id = db.Column(MySQLUUID, primary_key=True, default=uuid.uuid4)
    user_id = db.Column(MySQLUUID, db.ForeignKey('user.id'), nullable=False, index=True) # Foreign key to the User

    # Provider identification (composite unique constraint)
    task_user_email = db.Column(db.String(255), nullable=True, index=True) # Email associated with the task provider account (e.g., Google account email for Google Tasks)
    provider = db.Column(db.String(50), nullable=False)  # 'todoist', 'google_tasks', 'outlook', 'sqlite'
    provider_task_id = db.Column(db.String(255), nullable=False)  # ID from the provider

    # Task content
    title = db.Column(db.String(500), nullable=False)
    description = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(50), nullable=False)  # 'active', 'completed'
    due_date = db.Column(db.DateTime, nullable=True)
    priority = db.Column(db.Integer, nullable=True)  # 1=low, 2=medium, 3=high, 4=urgent

    # Organizational info
    project_id = db.Column(db.String(255), nullable=True)  # Provider's project ID
    project_name = db.Column(db.String(255), nullable=True)
    parent_id = db.Column(db.String(255), nullable=True)  # For hierarchical tasks
    section_id = db.Column(db.String(255), nullable=True)

    # Ordering info
    list_type = db.Column(db.String(50), default='unprioritized')  # 'prioritized' or 'unprioritized'
    position = db.Column(db.Integer, default=0)

    # Change tracking
    content_hash = db.Column(db.String(64), nullable=False)  # Hash of task content to detect changes
    last_synced = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Composite unique constraint
    __table_args__ = (
        # Ensure a task from a specific provider account for a specific app user is unique
        db.UniqueConstraint('user_id', 'task_user_email', 'provider', 'provider_task_id', name='uq_user_id_task_user_provider_task'),
    )

    @classmethod
    def create_or_update_from_provider_task(cls, user_id, task_user_email, provider, provider_task):
        """Create or update a task from provider data.

        Args:
            user_id: The user's database ID
            task_user_email: The email associated with the task provider account
            provider: Provider name ('todoist', 'google_tasks', etc.)
            provider_task: Task object from the provider

        Returns:
            Tuple[Task, bool]: The task object and whether it was created or updated
        """
        logger.debug(f"[SYNC] Processing task from {provider}: id={provider_task.id}, title='{provider_task.title}', status='{provider_task.status}'")

        # Log detailed information about the incoming task status
        logger.info(f"[SYNC] Incoming provider task status from {provider}: id={provider_task.id}, status='{provider_task.status}'")

        # Calculate content hash to detect changes
        task_content = {
            'title': provider_task.title,
            'status': provider_task.status,
            'due_date': provider_task.due_date.isoformat() if provider_task.due_date else None,
            'priority': provider_task.priority,
            'project_id': provider_task.project_id,
            'parent_id': getattr(provider_task, 'parent_id', None),
            'section_id': getattr(provider_task, 'section_id', None)
        }
        content_hash = hashlib.sha256(json.dumps(task_content, sort_keys=True).encode()).hexdigest()

        # Look for existing task with same provider/provider_task_id
        existing_task = cls.query.filter_by(
            user_id=user_id,
            provider=provider,
            provider_task_id=provider_task.id
        ).first()
        # TODO: Decide if we should also filter by task_user_email here if it's provided and not null? (Note: app_login changed to user_id)
        # existing_task = cls.query.filter_by(
        #     user_id=user_id,
        #     task_user_email=task_user_email,
        #     provider=provider,
        #     provider_task_id=provider_task.id
        # ).first()

        if existing_task:
            logger.debug(f"[SYNC] Found existing task in database: id={existing_task.id}, status='{existing_task.status}'")

            # Check if status has changed
            status_changed = existing_task.status != provider_task.status
            hash_changed = existing_task.content_hash != content_hash

            # Log status change and hash change information
            logger.debug(f"[SYNC] Task {provider_task.id} comparison: status_changed={status_changed}, hash_changed={hash_changed}")
            logger.debug(f"[SYNC] Task {provider_task.id} content hash: db={existing_task.content_hash}, new={content_hash}")

            # Track if we made any updates
            updated = False

            # Log status changes specifically
            if status_changed:
                # If only status changed, update just that field
                logger.info(f"[SYNC] Status-only change for task {provider_task.id}: old='{existing_task.status}', new='{provider_task.status}'")

                existing_task.status = provider_task.status
                existing_task.last_synced = datetime.utcnow()

                # Commit status changes
                db.session.commit()
                logger.info(f"[SYNC] Committed status change for task {provider_task.id} to database")
                updated = True

            # Check if content has changed or status specifically has changed
            if existing_task.content_hash != content_hash:
                # Log hash differences for debugging
                logger.info(f"[SYNC] Content hash changed for task {provider_task.id}: old={existing_task.content_hash}, new={content_hash}")

                # Update task content
                existing_task.title = provider_task.title
                existing_task.status = provider_task.status
                existing_task.due_date = provider_task.due_date
                existing_task.priority = provider_task.priority
                existing_task.project_id = provider_task.project_id
                existing_task.project_name = getattr(provider_task, 'project_name', None)
                existing_task.parent_id = getattr(provider_task, 'parent_id', None)
                existing_task.section_id = getattr(provider_task, 'section_id', None)
                existing_task.content_hash = content_hash
                existing_task.last_synced = datetime.utcnow()
                # Update task_user_email if it has changed or wasn't set before
                if existing_task.task_user_email != task_user_email:
                     existing_task.task_user_email = task_user_email

                db.session.commit()
                updated = True

            return existing_task, updated
        else:
            # Create new task
            new_task = cls(
                user_id=user_id,
                task_user_email=task_user_email,
                provider=provider,
                provider_task_id=provider_task.id,
                title=provider_task.title,
                status=provider_task.status,
                due_date=provider_task.due_date,
                priority=provider_task.priority,
                project_id=provider_task.project_id,
                project_name=getattr(provider_task, 'project_name', None),
                parent_id=getattr(provider_task, 'parent_id', None),
                section_id=getattr(provider_task, 'section_id', None),
                content_hash=content_hash,
                list_type='unprioritized',  # New tasks start unprioritized
                position=0  # Will be updated by position calculation
            )

            db.session.add(new_task)
            db.session.commit()

            # Calculate position for the new task
            cls.add_to_list(new_task.id, 'unprioritized')

            return new_task, True

    @classmethod
    def sync_task_deletions(cls, user_id, provider, current_provider_task_ids):
        """Remove tasks that no longer exist in the provider.

        Args:
            user_id: The user's database ID
            provider: Provider name
            current_provider_task_ids: List of current task IDs from the provider
        """
        # Find tasks in our database that aren't in the current provider list
        deleted_tasks = cls.query.filter(
            cls.user_id == user_id,
            cls.provider == provider,
            ~cls.provider_task_id.in_(current_provider_task_ids)
        ).all()

        # Delete these tasks
        for task in deleted_tasks:
            db.session.delete(task)

        db.session.commit()

    @classmethod
    def get_user_tasks_by_list(cls, user_id):
        """Get prioritized, unprioritized, and completed task lists for a user.

        Args:
            user_id: The user's database ID

        Returns:
            tuple: (prioritized_tasks, unprioritized_tasks, completed_tasks)
        """
        # Get prioritized active tasks
        prioritized = cls.query.filter_by(
            user_id=user_id,
            list_type='prioritized',
            status='active'
        ).order_by(cls.position).all()

        # Get unprioritized active tasks
        unprioritized = cls.query.filter_by(
            user_id=user_id,
            list_type='unprioritized',
            status='active'
        ).order_by(cls.position).all()
        
        # Get completed tasks (from both prioritized and unprioritized lists)
        completed = cls.query.filter_by(
            user_id=user_id,
            status='completed'
        ).order_by(cls.position).all()

        return (prioritized, unprioritized, completed)

    @classmethod
    def move_task(cls, task_id, destination, position=None):
        """Move a task between lists or update its position.

        Args:
            task_id: The task's database ID
            destination: 'prioritized', 'unprioritized', or 'completed'
            position: Optional position in the new list
        """
        task = cls.query.filter_by(id=task_id).first()
        if not task:
            raise ValueError(f"Task with ID {task_id} not found")

        # If the task is already in this list, just update position
        same_list = (task.list_type == destination)

        # Begin a transaction
        db.session.begin_nested()

        try:
            # If position is not specified, place at the end
            if position is None:
                # Find the highest position in the destination list
                max_position_result = db.session.query(db.func.max(cls.position))\
                    .filter_by(user_id=task.user_id, list_type=destination).first()
                max_position = max_position_result[0] if max_position_result[0] is not None else -1
                position = max_position + 1

            # Update positions of other tasks in the destination list
            if not same_list or position < task.position:
                cls.query.filter(
                    cls.user_id == task.user_id,
                    cls.list_type == destination,
                    cls.id != task_id,
                    cls.position >= position
                ).update({
                    cls.position: cls.position + 1
                }, synchronize_session=False)

            # If moving to the same list but earlier position, adjust the position
            if same_list and position < task.position:
                actual_position = position
            elif same_list and position > task.position:
                # When moving later in same list, account for the shift
                tasks_between = cls.query.filter(
                    cls.user_id == task.user_id,
                    cls.list_type == destination,
                    cls.position > task.position,
                    cls.position <= position
                ).count()
                actual_position = position - tasks_between
            else:
                actual_position = position

            # Update the task's list and position
            task.list_type = destination
            task.position = actual_position

            # Commit the transaction
            db.session.commit()
            return True
        except Exception as e:
            # Rollback in case of error
            db.session.rollback()
            raise e

    @classmethod
    def add_to_list(cls, task_id, list_type='unprioritized'):
        """Add a task to a list at the end.

        Args:
            task_id: The task's database ID
            list_type: 'prioritized', 'unprioritized', or 'completed'
        """
        return cls.move_task(task_id, list_type)

    @classmethod
    def update_task_order(cls, user_id, list_type, task_positions):
        """Update the order of multiple tasks in a list.

        Args:
            user_id: The user's database ID
            list_type: 'prioritized', 'unprioritized', or 'completed'
            task_positions: Dict mapping task IDs to positions
        """
        # Begin a transaction
        db.session.begin_nested()

        try:
            for task_id, position in task_positions.items():
                cls.query.filter_by(id=task_id, user_id=user_id).update({
                    'list_type': list_type,
                    'position': position
                })

            # Commit the transaction
            db.session.commit()
            return True
        except Exception as e:
            # Rollback in case of error
            db.session.rollback()
            raise e

    def to_dict(self):
        """Convert task to dictionary representation."""
        return {
            'id': self.id, # This is the internal DB id, maybe rename to db_id?
            'user_id': self.user_id,
            'task_user_email': self.task_user_email,
            'provider': self.provider,
            'provider_task_id': self.provider_task_id,
            'title': self.title,
            'description': self.description,
            'status': self.status,
            'due_date': self.due_date.isoformat() if self.due_date else None,
            'priority': self.priority,
            'project_id': self.project_id,
            'project_name': self.project_name,
            'parent_id': self.parent_id,
            'section_id': self.section_id,
            'list_type': self.list_type,
            'position': self.position,
            'last_synced': self.last_synced.isoformat() if self.last_synced else None
        }

# --- TaskAccount Model ---

class TaskAccount(db.Model):
    """Stores credentials (API key or OAuth tokens) for Task providers linked to a user."""
    __tablename__ = 'task_accounts'
    id = Column(MySQLUUID, primary_key=True, default=uuid.uuid4)
    user_id = Column(MySQLUUID, ForeignKey('user.id'), nullable=False, index=True)
    provider_name = Column(String(50), nullable=False, index=True) # e.g., 'todoist', 'google_tasks', 'outlook'
    # Email associated with the provider account (e.g., Google account email).
    # For providers like Todoist using API key, this stores the user's app_login.
    task_user_email = Column(String(255), nullable=False, index=True)

    # Credentials - store one type based on provider needs
    api_key = Column(Text, nullable=True) # For simple API key auth (e.g., Todoist)
    token = Column(Text, nullable=True) # OAuth access token
    refresh_token = Column(Text, nullable=True) # OAuth refresh token
    expires_at = Column(DateTime, nullable=True) # OAuth token expiry timestamp
    scopes = Column(Text, nullable=True) # OAuth scopes granted

    # Timestamps & Status
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    needs_reauth = Column(db.Boolean, nullable=False, default=False) # Flag if re-authentication is needed
    is_primary = Column(db.Boolean, default=False, nullable=False) # Whether this is the user's primary task account for this provider type

    # Define the relationship to the User model using back_populates
    user = relationship("User", back_populates="task_accounts")

    # Unique constraint: A user can link one account per provider/email combination.
    __table_args__ = (UniqueConstraint('user_id', 'provider_name', 'task_user_email', name='uq_user_provider_email'),)

    def __repr__(self):
        return f"<TaskAccount(user_id='{self.user_id}', provider='{self.provider_name}', email='{self.task_user_email}')>"

    @classmethod
    @classmethod
    def get_account(cls, user_id, provider_name: str, task_user_email: str):
        """Retrieve the task account for a specific user, provider, and provider email."""
        return cls.query.filter_by(
            user_id=user_id,
            provider_name=provider_name,
            task_user_email=task_user_email
        ).first()

    @classmethod
    def set_account(cls, user_id, provider_name: str, task_user_email: str, credentials: dict):
        """Create or update the task account credentials for a user, provider, and email.
           The `credentials` dict should contain the relevant keys ('api_key', 'token', etc.).
        """
        account = cls.get_account(user_id, provider_name, task_user_email)

        if not account:
            account = cls(
                user_id=user_id,
                provider_name=provider_name,
                task_user_email=task_user_email
            )
            db.session.add(account)

        # Update fields based on provided credentials dictionary
        # Use .get() with the current value as default to avoid overwriting with None if key is missing
        account.api_key = credentials.get('api_key', account.api_key)
        account.token = credentials.get('token', account.token)
        account.refresh_token = credentials.get('refresh_token', account.refresh_token)
        account.expires_at = credentials.get('expires_at', account.expires_at)
        account.scopes = credentials.get('scopes', account.scopes)
        # Reset reauth flag when credentials are updated, default to False if not specified
        account.needs_reauth = credentials.get('needs_reauth', False)
        
        # Check if the user has any primary task accounts
        has_primary = cls.query.filter_by(
            user_id=user_id,
            is_primary=True
        ).first() is not None
        
        # If the user doesn't have any primary task accounts, set this one as primary
        if not has_primary:
            account.is_primary = True
            logger.info(f"Setting {provider_name} account for user {user_id} as primary (no primary account exists)")

        return account # Return the account instance, caller should commit session

    @classmethod
    @classmethod
    def delete_account(cls, user_id, provider_name: str, task_user_email: str):
        """Delete the task account for a specific user, provider, and email."""
        account = cls.get_account(user_id, provider_name, task_user_email)
        if account:
            db.session.delete(account)
            return True # Return True if deleted, caller should commit session
        return False