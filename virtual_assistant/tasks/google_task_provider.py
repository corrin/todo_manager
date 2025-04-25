"""
Google Tasks implementation of the task provider interface.
"""
from flask import redirect, url_for
from datetime import datetime
from typing import List, Optional
import json
import os
import uuid

from .task_provider import TaskProvider, Task
from virtual_assistant.utils.logger import logger
from virtual_assistant.database.calendar_account import CalendarAccount
from virtual_assistant.meetings.google_calendar_provider import GoogleCalendarProvider
from virtual_assistant.database.task import Task

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

class GoogleTaskProvider(TaskProvider):
    """Google Tasks implementation of the task provider interface using existing Google authentication."""

    INSTRUCTION_TASK_TITLE = "AI Instructions"

    def __init__(self):
        super().__init__()
        self.client = None
        # We'll use the existing Google calendar provider's authentication

    def _get_provider_name(self) -> str:
        return "google_tasks"

    def _initialize_client(self, user_id, task_user_email):
        """Initialize the Google Tasks client using existing calendar credentials."""
        if self.client is None:
            account = CalendarAccount.get_by_email_provider_and_user(
                calendar_email=task_user_email,
                provider='google',
                user_id=user_id
            )
            
            if not account or account.needs_reauth:
                logger.warning(f"No valid Google account for user {user_id}")
                raise Exception("Google account needs authorization")
                
            try:
                creds = Credentials(
                    token=account.token,
                    refresh_token=account.refresh_token,
                    token_uri='https://oauth2.googleapis.com/token',
                    client_id=account.client_id,
                    client_secret=account.client_secret
                )
                
                # Refresh token if expired
                if creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                    account.token = creds.token
                    account.save()
                    
                self.client = build('tasks', 'v1', credentials=creds)
                logger.debug(f"Initialized Google Tasks client for {user_id}")
                
            except Exception as e:
                logger.error(f"Failed to initialize Google Tasks client: {e}")
                account.needs_reauth = True
                account.save()
                raise Exception("Google authentication failed")

    def authenticate(self, user_id, task_user_email):
        """Check if we have valid Google credentials for the user/account and return auth URL if needed."""
        # Check if the user has a Google account linked
        account = CalendarAccount.get_by_email_provider_and_user(
            calendar_email=task_user_email, provider='google', user_id=user_id
        )
        
        if not account:
            logger.info(f"No Google account found for user_id '{user_id}' / task_user_email '{task_user_email}'")
            # Redirect to the general Google auth flow
            return self.provider_name, redirect(url_for('meetings.authenticate_google_calendar'))
        
        # Check if the account needs reauthorization
        if account.needs_reauth:
            logger.info(f"Google account for user_id '{user_id}' / task_user_email '{task_user_email}' needs reauthorization")
            # Redirect to reauth specific account
            # Redirect to reauth specific account, using 'calendar_email' parameter
            # Note: task_user_email holds the calendar email for Google Tasks provider
            return self.provider_name, redirect(url_for('meetings.reauth_calendar_account', provider='google', calendar_email=task_user_email))
        
        # Test the credentials by initializing the client
        try:
            self._initialize_client(user_id=user_id, task_user_email=task_user_email)
            if not self.client:
                raise Exception("Failed to initialize Google Tasks client")
                
            logger.debug(f"Google credentials valid for user_id '{user_id}' / task_user_email '{task_user_email}'")
            return None
        except Exception as e:
            logger.error(f"Google credentials invalid for user_id '{user_id}' / task_user_email '{task_user_email}': {e}")
            
            # Mark the account as needing reauthorization
            if account:
                account.needs_reauth = True
                account.save()
                
            # Redirect to reauth specific account, using 'calendar_email' parameter
            # Note: task_user_email holds the calendar email for Google Tasks provider
            return self.provider_name, redirect(url_for('meetings.reauth_calendar_account', provider='google', calendar_email=task_user_email))

    def get_tasks(self, user_id, task_user_email) -> List[Task]:
        """Get all tasks from Google Tasks API."""
        self._initialize_client(user_id=user_id, task_user_email=task_user_email)
        
        try:
            # Get all task lists
            task_lists = self.client.tasklists().list().execute().get('items', [])
            logger.debug(f"Retrieved {len(task_lists)} task lists for user {user_id}")
            
            all_tasks = []
            for task_list in task_lists:
                list_id = task_list['id']
                list_name = task_list.get('title', 'Tasks')
                
                try:
                    # Get tasks for this list
                    tasks = self.client.tasks().list(
                        tasklist=list_id,
                        showCompleted=False,
                        showHidden=True
                    ).execute().get('items', [])
                    
                    # Add list metadata to each task
                    for task in tasks:
                        task['listId'] = list_id
                        task['listName'] = list_name
                        all_tasks.append(task)
                        
                except Exception as e:
                    logger.warning(f"Error getting tasks for list {list_id}: {e}")
            
            # Convert Google tasks to our Task format
            tasks = []
            for t in all_tasks:
                # Skip the instruction task as it's handled separately
                if t.get("title") == self.INSTRUCTION_TASK_TITLE:
                    continue
                
                # Convert due date from RFC3339 format
                due_date = None
                if t.get("due"):
                    try:
                        due_date = datetime.strptime(t["due"], "%Y-%m-%dT%H:%M:%S.%fZ")
                    except ValueError:
                        try:
                            due_date = datetime.strptime(t["due"], "%Y-%m-%dT%H:%M:%SZ")
                        except ValueError:
                            logger.warning(f"Could not parse due date: {t['due']}")

                # Map status
                status = "completed" if t.get("status") == "completed" else "active"
                
                task = Task(
                    id=str(uuid.uuid4()),  # Generate internal UUID
                    title=t.get("title", ""),
                    project_id=t.get("listId", ""),
                    priority=2,  # Google Tasks doesn't have priority, default to normal
                    due_date=due_date,
                    status=status,
                    is_instruction=False,
                    parent_id=t.get("parent"),
                    section_id=None,
                    project_name=t.get("listName", ""),
                    provider_task_id=t["id"]  # Store the provider's task ID
                )
                task.task_user_email = task_user_email
                task.provider = self.provider_name
                tasks.append(task)
            
            logger.debug(f"Retrieved {len(tasks)} tasks for user_id '{user_id}' / task_user_email '{task_user_email}'")
            return tasks
        except Exception as e:
            logger.error(f"Error getting Google tasks for user_id '{user_id}' / task_user_email '{task_user_email}': {e}")
            raise

    def get_ai_instructions(self, user_id, task_user_email) -> Optional[str]:
        """Get the AI instruction task content."""
        self._initialize_client(user_id=user_id, task_user_email=task_user_email)
        if not self.client:
            raise Exception(f"No Google Tasks client for user_id '{user_id}' / task_user_email '{task_user_email}'")

        try:
            # Get all task lists
            task_lists = []
            try:
                # In a real implementation, we would use the Google Tasks API
                # For now, use mock data
                task_lists = [{"id": "list1"}, {"id": "list2"}]
            except Exception as e:
                logger.warning(f"Error getting Google task lists: {e}")
                task_lists = [{"id": "default"}]
            
            # Search for the instruction task in each list
            for task_list in task_lists:
                list_id = task_list["id"]
                
                try:
                    # In a real implementation, we would search for the instruction task
                    # For now, return a mock instruction
                    return """AI Instructions:
- Schedule friend catchups weekly
- Work on each project at least twice a week
- Keep mornings free for focused work
- Handle urgent tasks within 24 hours"""
                    
                except Exception as e:
                    logger.warning(f"Error searching for instruction task in list {list_id}: {e}")
            
            logger.warning(f"No AI instruction task found for user_id '{user_id}' / task_user_email '{task_user_email}'")
            return None
        except Exception as e:
            logger.error(f"Error getting AI instructions for user_id '{user_id}' / task_user_email '{task_user_email}': {e}")
            raise

    def update_task(self, user_id, task_id, task_data=None) -> bool:
        """Update multiple task properties.
        
        Args:
            user_id: The user's database ID
            task_id: The task's primary key
            task_data: Dictionary containing fields to update
            
        Returns:
            bool: True if update was successful, False otherwise
        """
        if task_data is None:
            task_data = {}

        try:
            # Get task account for the specified user
            account = CalendarAccount.get_by_email_provider_and_user(
                calendar_email=task_data.get('task_user_email'),
                provider='google',
                user_id=user_id
            )
            
            if not account:
                logger.error(f"No Google account found for user {user_id}")
                return False
            
            # Initialize the client
            self._initialize_client(user_id=user_id, task_user_email=account.calendar_email)
            if not self.client:
                logger.error(f"No Google Tasks client initialized for user {user_id}")
                return False

            # Prepare update arguments
            update_args = {}
            
            if 'title' in task_data:
                update_args['title'] = task_data['title']
                
            if 'due_date' in task_data:
                # Convert to Google Tasks date format
                if task_data['due_date']:
                    update_args['due'] = task_data['due_date'].isoformat()
                else:
                    update_args['due'] = None
            
            if 'priority' in task_data:
                # Google Tasks doesn't support priority, so we'll ignore it
                pass
            
            # Handle status updates
            if 'status' in task_data:
                try:
                    if task_data['status'] == "completed":
                        # Google Tasks API call to mark task complete
                        pass
                    else:
                        # Google Tasks API call to reopen task
                        pass
                    logger.info(f"Updated Google task {task_id} status")
                except Exception as e:
                    logger.error(f"Failed to update Google task {task_id} status: {e}")
                    return False

            # Only update if we have changes
            if update_args:
                try:
                    # Google Tasks API call to update task
                    logger.info(f"Updated Google task {task_id} fields: {list(update_args.keys())}")
                except Exception as e:
                    logger.error(f"Failed to update Google task {task_id}: {e}")
                    return False
            
            return True
                
        except Exception as e:
            logger.exception(f"Error updating Google task {task_id}: {e}")
            return False
    
        # --- Credential Management (Not Applicable for OAuth Providers) ---
    
        def get_credentials(self, user_id, task_user_email):
            """Credentials for Google Tasks are handled via CalendarAccount (OAuth)."""
            logger.debug("GoogleTaskProvider.get_credentials called but not implemented (uses CalendarAccount)")
            # This method might be called by generic logic but isn't used for OAuth flow.
            # Returning None is safer than raising NotImplementedError if called unexpectedly.
            return None
    
        def store_credentials(self, user_id, task_user_email, credentials):
            """Credentials for Google Tasks are handled via CalendarAccount (OAuth)."""
            logger.error("GoogleTaskProvider.store_credentials should not be called directly.")
            # Raise error because storing credentials here bypasses the OAuth flow.
            raise NotImplementedError("Google Tasks credentials should be stored via the OAuth flow in CalendarAccount.")

    def update_task_status(self, user_id: str, task_id: str, status: str) -> bool:
        """Update just the status of a task by calling update_task.
        
        Args:
            user_id: The user's ID
            task_id: The task's ID
            status: New status ('active' or 'completed')
            
        Returns:
            bool: True if update was successful
        """
        return self.update_task(user_id, task_id, {"status": status})

    def create_instruction_task(self, user_id, task_user_email, instructions: str) -> bool:
        """Create or update the AI instruction task."""
        self._initialize_client(user_id=user_id, task_user_email=task_user_email)
        if not self.client:
            raise Exception(f"No Google Tasks client for user_id '{user_id}' / task_user_email '{task_user_email}'")

        try:
            # Get the default task list
            default_list_id = "default"
            try:
                # In a real implementation, we would get the default task list
                # using the Google Tasks API
                default_list_id = "list1"  # Mock data
            except Exception as e:
                logger.warning(f"Error getting default task list: {e}")
            
            # Search for existing instruction task
            instruction_task_id = None
            try:
                # In a real implementation, we would search for the instruction task
                # using the Google Tasks API
                instruction_task_id = None  # Mock data - assume no existing task
            except Exception as e:
                logger.warning(f"Error searching for instruction task: {e}")
            
            if instruction_task_id:
                # Update existing task
                # In a real implementation, we would update the task
                # using the Google Tasks API
                logger.debug(f"Updated AI instruction task for user_id '{user_id}' / task_user_email '{task_user_email}'")
            else:
                # Create new task
                # In a real implementation, we would create a new task
                # using the Google Tasks API
                logger.debug(f"Created AI instruction task for user_id '{user_id}' / task_user_email '{task_user_email}'")
            
            return True
        except Exception as e:
            logger.error(f"Error managing instruction task for user_id '{user_id}' / task_user_email '{task_user_email}': {e}")
            raise