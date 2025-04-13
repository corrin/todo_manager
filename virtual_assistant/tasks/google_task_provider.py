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
        """Initialize or refresh the Google Tasks client using existing Google credentials."""
        if self.client is None:
            # Get the Google account for this specific user_id and task_user_email
            account = CalendarAccount.get_by_email_provider_and_user(
                calendar_email=task_user_email, provider='google', user_id=user_id
            )
            
            if account and not account.needs_reauth:
                # In a real implementation, we would create a Google Tasks client
                # using the existing credentials
                self.client = True  # Stub client
                logger.debug(f"Initialized Google Tasks client for user_id '{user_id}' / task_user_email '{task_user_email}' using existing Google credentials")
            else:
                logger.warning(f"No Google account found for user_id '{user_id}' / task_user_email '{task_user_email}' or needs reauth")

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
        if not self.client:
            raise Exception(f"No Google Tasks client for user_id '{user_id}' / task_user_email '{task_user_email}'")

        try:
            # Get all task lists (folders)
            task_lists = []
            try:
                # In a real implementation, we would use the Google Tasks API
                # For now, use mock data
                task_lists = [
                    {"id": "list1", "title": "Work"},
                    {"id": "list2", "title": "Personal"}
                ]
                logger.debug(f"Retrieved {len(task_lists)} task lists for user_id '{user_id}' / task_user_email '{task_user_email}'")
            except Exception as e:
                logger.error(f"Error getting Google task lists: {e}")
                # Instead of silently falling back, raise an exception that will be shown to the user
                raise Exception(f"Could not retrieve your Google task lists: {e}")
            
            # Get tasks from each list
            all_tasks = []
            for task_list in task_lists:
                list_id = task_list["id"]
                list_name = task_list["title"]
                
                try:
                    # In a real implementation, we would use the Google Tasks API
                    # For now, use mock data
                    list_tasks = []
                    if list_id == "list1":
                        list_tasks = [
                            {
                                "id": "task1",
                                "title": "Finish Google integration",
                                "notes": "Need to complete by end of week",
                                "due": "2025-04-01T00:00:00Z",
                                "status": "needsAction",
                                "parent": None
                            },
                            {
                                "id": "task2",
                                "title": "Test API endpoints",
                                "notes": "Focus on error handling",
                                "due": "2025-03-25T00:00:00Z",
                                "status": "needsAction",
                                "parent": "task1"
                            }
                        ]
                    elif list_id == "list2":
                        list_tasks = [
                            {
                                "id": "task3",
                                "title": "Schedule dentist appointment",
                                "notes": "",
                                "due": None,
                                "status": "needsAction",
                                "parent": None
                            }
                        ]
                    
                    # Add list ID and name to each task
                    for task in list_tasks:
                        task["listId"] = list_id
                        task["listName"] = list_name
                        all_tasks.append(task)
                        
                except Exception as e:
                    logger.warning(f"Error getting tasks for list {list_id}: {e}")
            
            # Convert Google tasks to our Task format
            tasks = []
            for t in all_tasks:
                # Skip the instruction task as it's handled separately
                if t.get("title") == self.INSTRUCTION_TASK_TITLE:
                    continue
                
                # Convert due date
                due_date = None
                if t.get("due"):
                    due_date_str = t.get("due")
                    if due_date_str:
                        due_date = datetime.fromisoformat(due_date_str.replace("Z", "+00:00"))

                # Map status
                status_map = {
                    "needsAction": "active",
                    "completed": "completed"
                }
                status = status_map.get(t.get("status", "needsAction"), "active")
                # Generate a UUID for the task
                task_uuid = str(uuid.uuid4())

                task = Task(
                    id=task_uuid,  # Use a UUID for the internal ID
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

    def update_task_status(self, user_id, task_id, task_user_email=None, provider_task_id=None, status: str = None) -> bool:
        """Update task completion status."""
        # Look up the task to get provider_task_id and task_user_email
        task = Task.query.filter_by(id=task_id, user_id=user_id).first()
        if not task:
            raise ValueError(f"Task with ID {task_id} not found")
            
        # Get the provider-specific information
        provider_task_id = task.provider_task_id
        task_user_email = task.task_user_email
        provider = task.provider # Should be Google Tasks

        # Initialize the client
        self._initialize_client(user_id=user_id, task_user_email=task_user_email)
        if not self.client:
            raise Exception(f"No Google Tasks client for user_id '{user_id}' / task_user_email '{task_user_email}'")

        try:
            # Map our status to Google Tasks status
            google_status = "completed" if status == "completed" else "needsAction"
            
            # Try to verify the task exists first
            try:
                # In a real implementation, we would get the task to verify it exists
                # using the Google Tasks API
                
                # Mock check - in a real implementation, this would be replaced with an API call
                task_exists = True  # Placeholder - would check if task exists
                
                if task_exists:
                    # In a real implementation, we would update the task status
                    # using the Google Tasks API with provider_task_id
                    
                    logger.debug(f"Updated task (UUID: {task_id}, provider: Google, provider_task_id: {provider_task_id}) status to {status} for user_id '{user_id}' / task_user_email '{task_user_email}'")
                    return True
                else:
                    raise Exception(f"Task with provider_task_id {provider_task_id} not found in Google Tasks")
                    
            except Exception as task_error:
                error_msg = str(task_error).lower()
                if "not found" in error_msg or "404" in error_msg:
                    raise Exception(f"Task with provider_task_id {provider_task_id} not found in Google Tasks. It may have been deleted or synced incorrectly. Try refreshing your tasks.")
                # For other errors, log and propagate
                logger.error(f"Error updating Google Tasks task status for user_id '{user_id}' / task_user_email '{task_user_email}': {task_error}")
                raise
                
        except Exception as e:
            # Check for common API errors and provide better messages
            error_msg = str(e).lower()
            
            if "quota" in error_msg or "rate limit" in error_msg or "429" in error_msg:
                raise Exception("Google Tasks API rate limit reached. Please wait a moment and try again.")
            elif "authentication" in error_msg or "unauthorized" in error_msg or "401" in error_msg:
                raise Exception("Google Tasks authentication error. Please check your Google account connection in Settings.")
            elif "network" in error_msg or "timeout" in error_msg or "connection" in error_msg:
                raise Exception("Network error when connecting to Google Tasks. Please check your internet connection.")
            else:
                # If not a specific known error, log the original error and pass it along
                logger.error(f"Error updating task status for user_id '{user_id}' / task_user_email '{task_user_email}': {e}")
                raise
    
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