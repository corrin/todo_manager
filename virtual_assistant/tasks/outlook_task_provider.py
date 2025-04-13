"""
Outlook implementation of the task provider interface.
"""
from flask import redirect, url_for
from datetime import datetime
from typing import List, Optional
import json
import os

from .task_provider import TaskProvider, Task
from virtual_assistant.utils.logger import logger
from virtual_assistant.database.calendar_account import CalendarAccount
from virtual_assistant.database.task import Task
from virtual_assistant.meetings.o365_calendar_provider import AccessTokenCredential
from msgraph import GraphServiceClient


class OutlookTaskProvider(TaskProvider):
    """Outlook implementation of the task provider interface using existing O365 authentication."""

    INSTRUCTION_TASK_TITLE = "AI Instructions"

    def __init__(self):
        super().__init__()
        self.client = None
        # We'll use the existing O365 calendar provider's authentication

    def _get_provider_name(self) -> str:
        return "outlook"

    def _initialize_client(self, user_id, task_user_email):
        """Initialize or refresh the Microsoft Graph client using existing O365 credentials."""
        if self.client is None:
            # Get the O365 account for this specific app_login and task_user_email
            account = CalendarAccount.get_by_email_provider_and_user(
                calendar_email=task_user_email, provider='o365', user_id=user_id
            )
            
            if account and account.token:  # Using token instead of access_token
                # Create a credential using the existing access token
                credential = AccessTokenCredential(account.token)
                
                # Create a Graph client using the credential
                self.client = GraphServiceClient(credential)
                logger.debug(f"Initialized Microsoft Graph client for user_id '{user_id}' / task_user_email '{task_user_email}' using existing O365 credentials")
            else:
                logger.warning(f"No O365 account found for user_id '{user_id}' / task_user_email '{task_user_email}' or missing token")

    def authenticate(self, user_id, task_user_email):
        """Check if we have valid O365 credentials for the user/account and return auth URL if needed."""
        # Check if the user has an O365 account linked
        account = CalendarAccount.get_by_email_provider_and_user(
            calendar_email=task_user_email, provider='o365', user_id=user_id
        )
        
        if not account:
            logger.info(f"No O365 account found for user_id '{user_id}' / task_user_email '{task_user_email}'")
            # Redirect to the general O365 auth flow
            return self.provider_name, redirect(url_for('meetings.authenticate_o365_calendar'))
        
        # Check if the account needs reauthorization
        if account.needs_reauth:
            logger.info(f"O365 account for user_id '{user_id}' / task_user_email '{task_user_email}' needs reauthorization")
            # Redirect to reauth specific account, using 'calendar_email' parameter
            return self.provider_name, redirect(url_for('meetings.reauth_calendar_account', provider='o365', calendar_email=account.calendar_email))
        
        # Test the credentials by initializing the client
        try:
            self._initialize_client(user_id=user_id, task_user_email=task_user_email)
            if not self.client:
                raise Exception("Failed to initialize Microsoft Graph client")
                
            logger.debug(f"O365 credentials valid for user_id '{user_id}' / task_user_email '{task_user_email}'")
            return None
        except Exception as e:
            logger.error(f"O365 credentials invalid for user_id '{user_id}' / task_user_email '{task_user_email}': {e}")
            
            # Mark the account as needing reauthorization
            if account:
                account.needs_reauth = True
                account.save()
                
            return self.provider_name, redirect(url_for('meetings.reauth_calendar_account', provider='o365', email=account.calendar_email))

    def get_tasks(self, user_id, task_user_email) -> List[Task]:
        """Get all tasks from Outlook using Microsoft Graph API."""
        self._initialize_client(user_id=user_id, task_user_email=task_user_email)
        if not self.client:
            raise Exception(f"No Microsoft Graph client for user_id '{user_id}' / task_user_email '{task_user_email}'")

        try:
            # Get all task lists (folders)
            # Get all task lists (folders)
            try:
                # Correct API path for Microsoft Graph
                task_lists_response = self.client.me.outlook.tasks.folders.get()
                task_lists = task_lists_response.value
                logger.debug(f"Retrieved {len(task_lists)} task lists for user_id '{user_id}' / task_user_email '{task_user_email}'")
            except Exception as e:
                logger.error(f"Error getting Outlook task lists: {e}")
                # Instead of silently falling back, raise an exception that will be shown to the user
                raise Exception(f"Could not retrieve your Outlook task lists: {e}")
            
            # Get tasks from each list
            all_tasks = []
            for task_list in task_lists:
                list_id = task_list["id"]
                list_name = task_list["displayName"]
                
                try:
                    # Get tasks for this list using correct API path
                    tasks_response = self.client.me.outlook.tasks.folders.by_id(list_id).tasks.get()
                    list_tasks = tasks_response.value
                    
                    # Add list ID and name to each task
                    for task in list_tasks:
                        task_dict = task.to_dict()
                        task_dict["listId"] = list_id
                        task_dict["listName"] = list_name
                        all_tasks.append(task_dict)
                        
                except Exception as e:
                    logger.warning(f"Error getting tasks for list {list_id}: {e}")
            
            # Convert Outlook tasks to our Task format
            tasks = []
            for t in all_tasks:
                # Skip the instruction task as it's handled separately
                if t.get("subject") == self.INSTRUCTION_TASK_TITLE:
                    continue
                
                # Convert due date
                due_date = None
                if t.get("dueDateTime"):
                    due_date_str = t["dueDateTime"].get("dateTime")
                    if due_date_str:
                        due_date = datetime.fromisoformat(due_date_str.replace("Z", "+00:00"))

                # Map importance to priority
                priority_map = {
                    "low": 1,
                    "normal": 2,
                    "high": 3,
                    "urgent": 4
                }
                priority = priority_map.get(t.get("importance", "normal"), 2)

                # Map status
                status_map = {
                    "notStarted": "active",
                    "inProgress": "active",
                    "completed": "completed",
                    "waitingOnOthers": "active",
                    "deferred": "active"
                }
                status = status_map.get(t.get("status", "notStarted"), "active")

                # Get parent ID if available
                parent_id = None
                if t.get("parentReferences"):
                    parent_id = t["parentReferences"].get("id")

                task = Task(
                    id=t["id"],
                    title=t.get("subject", ""),
                    project_id=t.get("listId", ""),
                    priority=priority,
                    due_date=due_date,
                    status=status,
                    is_instruction=False,
                    parent_id=parent_id,
                    section_id=None,
                    project_name=t.get("listName", "")
                )
                tasks.append(task)
            
            logger.debug(f"Retrieved {len(tasks)} tasks for user_id '{user_id}' / task_user_email '{task_user_email}'")
            return tasks
        except Exception as e:
            logger.error(f"Error getting Outlook tasks for user_id '{user_id}' / task_user_email '{task_user_email}': {e}")
            raise

    def get_ai_instructions(self, user_id, task_user_email) -> Optional[str]:
        """Get the AI instruction task content."""
        self._initialize_client(user_id=user_id, task_user_email=task_user_email)
        if not self.client:
            raise Exception(f"No Microsoft Graph client for user_id '{user_id}' / task_user_email '{task_user_email}'")

        try:
            # Get all task lists
            try:
                task_lists_response = self.client.me.outlook.tasks.folders.get()
                task_lists = task_lists_response.value
            except Exception as e:
                logger.warning(f"Error getting Outlook task lists: {e}")
                return None
            
            # Search for the instruction task in each list
            for task_list in task_lists:
                list_id = task_list.id
                
                try:
                    # Search for the instruction task
                    filter_query = f"subject eq '{self.INSTRUCTION_TASK_TITLE}'"
                    tasks_response = self.client.me.outlook.tasks.folders.by_id(list_id).tasks.get(filter=filter_query)
                    instruction_tasks = tasks_response.value
                    
                    # If found, return the content
                    if instruction_tasks and len(instruction_tasks) > 0:
                        instruction_task = instruction_tasks[0]
                        if hasattr(instruction_task, 'body') and instruction_task.body:
                            return instruction_task.body.content
                    
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
        
        self._initialize_client(user_id=user_id, task_user_email=task_user_email)
        if not self.client:
            raise Exception(f"No Microsoft Graph client for user_id '{user_id}' / task_user_email '{task_user_email}'")

        try:
            # Map our status to Outlook status
            outlook_status = "completed" if status == "completed" else "notStarted"
            
            # Try to verify the task exists and update it
            try:
                # Get the task to verify it exists
                outlook_task = self.client.me.outlook.tasks.by_id(provider_task_id).get()
                
                # Update the task status
                self.client.me.outlook.tasks.by_id(provider_task_id).patch({"status": outlook_status})
                
                logger.debug(f"Updated task (UUID: {task_id}, provider: O365, provider_task_id: {provider_task_id}) status to {status} for user_id '{user_id}' / task_user_email '{task_user_email}'")
                return True
                    
            except Exception as task_error:
                error_msg = str(task_error).lower()
                if "not found" in error_msg or "404" in error_msg:
                    raise Exception(f"Task with provider_task_id {provider_task_id} not found in Outlook Tasks. It may have been deleted or synced incorrectly. Try refreshing your tasks.")
                # For other errors, log and propagate
                logger.error(f"Error updating Outlook Tasks task status for user_id '{user_id}' / task_user_email '{task_user_email}': {task_error}")
                raise
                
        except Exception as e:
            # Check for common API errors and provide better messages
            error_msg = str(e).lower()
            
            if "throttled" in error_msg or "rate limit" in error_msg or "429" in error_msg:
                raise Exception("Microsoft Graph API rate limit reached. Please wait a moment and try again.")
            elif "authentication" in error_msg or "unauthorized" in error_msg or "401" in error_msg:
                raise Exception("Outlook Tasks authentication error. Please check your Microsoft account connection in Settings.")
            elif "network" in error_msg or "timeout" in error_msg or "connection" in error_msg:
                raise Exception("Network error when connecting to Outlook Tasks. Please check your internet connection.")
            else:
                # If not a specific known error, log the original error and pass it along
                logger.error(f"Error updating task status for user_id '{user_id}' / task_user_email '{task_user_email}': {e}")
                raise

    def create_instruction_task(self, user_id, task_user_email, instructions: str) -> bool:
        """Create or update the AI instruction task."""
        self._initialize_client(user_id=user_id, task_user_email=task_user_email)
        if not self.client:
            raise Exception(f"No Microsoft Graph client for user_id '{user_id}' / task_user_email '{task_user_email}'")

        try:
            # Get the default task list
            try:
                task_lists_response = self.client.me.outlook.tasks.folders.get()
                if not task_lists_response.value:
                    raise Exception("No task lists found")
                default_list_id = task_lists_response.value[0].id
            except Exception as e:
                logger.error(f"Error getting default task list: {e}")
                raise Exception(f"Could not get default task list: {e}")
            
            # Search for existing instruction task
            instruction_task_id = None
            try:
                filter_query = f"subject eq '{self.INSTRUCTION_TASK_TITLE}'"
                tasks_response = self.client.me.outlook.tasks.folders.by_id(default_list_id).tasks.get(filter=filter_query)
                instruction_tasks = tasks_response.value
                if instruction_tasks and len(instruction_tasks) > 0:
                    instruction_task_id = instruction_tasks[0].id
            except Exception as e:
                logger.warning(f"Error searching for instruction task: {e}")
            
            if instruction_task_id:
                # Update existing task
                self.client.me.outlook.tasks.by_id(instruction_task_id).patch({
                    "body": {"content": instructions}
                })
                logger.debug(f"Updated AI instruction task for user_id '{user_id}' / task_user_email '{task_user_email}'")
            else:
                # Create new task
                new_task = {
                    "subject": self.INSTRUCTION_TASK_TITLE,
                    "body": {"content": instructions},
                    "importance": "high"
                }
                self.client.me.outlook.tasks.folders.by_id(default_list_id).tasks.post(new_task)
                logger.debug(f"Created AI instruction task for user_id '{user_id}' / task_user_email '{task_user_email}'")
            
            return True
        except Exception as e:
            logger.error(f"Error managing instruction task for user_id '{user_id}' / task_user_email '{task_user_email}': {e}")
            raise

    # --- Credential Management (Not Applicable for OAuth Providers) ---

    def get_credentials(self, user_id, task_user_email):
        """Credentials for Outlook are handled via CalendarAccount (OAuth)."""
        logger.debug("OutlookTaskProvider.get_credentials called but not implemented (uses CalendarAccount)")
        # This method might be called by generic logic but isn't used for OAuth flow.
        # Returning None is safer than raising NotImplementedError if called unexpectedly.
        return None

    def store_credentials(self, user_id, task_user_email, credentials):
        """Credentials for Outlook are handled via CalendarAccount (OAuth)."""
        logger.error("OutlookTaskProvider.store_credentials should not be called directly.")
        # Raise error because storing credentials here bypasses the OAuth flow.
        raise NotImplementedError("Outlook credentials should be stored via the OAuth flow in CalendarAccount.")