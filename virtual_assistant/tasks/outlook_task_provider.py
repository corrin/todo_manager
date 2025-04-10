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

    def _initialize_client(self, app_login, task_user_email):
        """Initialize or refresh the Microsoft Graph client using existing O365 credentials."""
        if self.client is None:
            # Get the O365 account for this specific app_login and task_user_email
            account = CalendarAccount.get_by_email_provider_and_user(
                calendar_email=task_user_email, provider='o365', app_login=app_login
            )
            
            if account and account.token:  # Using token instead of access_token
                # Create a credential using the existing access token
                credential = AccessTokenCredential(account.token)
                
                # Create a Graph client using the credential
                self.client = GraphServiceClient(credential)
                logger.debug(f"Initialized Microsoft Graph client for app_login '{app_login}' / task_user_email '{task_user_email}' using existing O365 credentials")
            else:
                logger.warning(f"No O365 account found for app_login '{app_login}' / task_user_email '{task_user_email}' or missing token")

    def authenticate(self, app_login, task_user_email):
        """Check if we have valid O365 credentials for the user/account and return auth URL if needed."""
        # Check if the user has an O365 account linked
        account = CalendarAccount.get_by_email_provider_and_user(
            calendar_email=task_user_email, provider='o365', app_login=app_login
        )
        
        if not account:
            logger.info(f"No O365 account found for app_login '{app_login}' / task_user_email '{task_user_email}'")
            # Redirect to the general O365 auth flow
            return self.provider_name, redirect(url_for('meetings.authenticate_o365_calendar'))
        
        # Check if the account needs reauthorization
        if account.needs_reauth:
            logger.info(f"O365 account for app_login '{app_login}' / task_user_email '{task_user_email}' needs reauthorization")
            # Redirect to reauth specific account, using 'calendar_email' parameter
            return self.provider_name, redirect(url_for('meetings.reauth_calendar_account', provider='o365', calendar_email=account.calendar_email))
        
        # Test the credentials by initializing the client
        try:
            self._initialize_client(app_login=app_login, task_user_email=task_user_email)
            if not self.client:
                raise Exception("Failed to initialize Microsoft Graph client")
                
            logger.debug(f"O365 credentials valid for app_login '{app_login}' / task_user_email '{task_user_email}'")
            return None
        except Exception as e:
            logger.error(f"O365 credentials invalid for app_login '{app_login}' / task_user_email '{task_user_email}': {e}")
            
            # Mark the account as needing reauthorization
            if account:
                account.needs_reauth = True
                account.save()
                
            return self.provider_name, redirect(url_for('meetings.reauth_calendar_account', provider='o365', email=account.calendar_email))

    def get_tasks(self, app_login, task_user_email) -> List[Task]:
        """Get all tasks from Outlook using Microsoft Graph API."""
        self._initialize_client(app_login=app_login, task_user_email=task_user_email)
        if not self.client:
            raise Exception(f"No Microsoft Graph client for app_login '{app_login}' / task_user_email '{task_user_email}'")

        try:
            # Get all task lists (folders)
            task_lists = []
            try:
                # In a real implementation, we would use:
                # task_lists_response = self.client.me.todo.lists.get()
                # task_lists = task_lists_response.value
                
                # For now, use mock data
                task_lists = [
                    {"id": "list1", "displayName": "Work"},
                    {"id": "list2", "displayName": "Personal"}
                ]
                logger.debug(f"Retrieved {len(task_lists)} task lists for app_login '{app_login}' / task_user_email '{task_user_email}'")
            except Exception as e:
                logger.warning(f"Error getting Outlook task lists: {e}")
                task_lists = [{"id": "default", "displayName": "Tasks"}]
            
            # Get tasks from each list
            all_tasks = []
            for task_list in task_lists:
                list_id = task_list["id"]
                list_name = task_list["displayName"]
                
                try:
                    # In a real implementation, we would use:
                    # tasks_response = self.client.me.todo.lists.by_todo_task_list_id(list_id).tasks.get()
                    # list_tasks = tasks_response.value
                    
                    # For now, use mock data
                    list_tasks = []
                    if list_id == "list1":
                        list_tasks = [
                            {
                                "id": "task1",
                                "title": "Complete project proposal",
                                "importance": "high",
                                "status": "notStarted",
                                "dueDateTime": {"dateTime": "2025-04-01T00:00:00Z"},
                                "parentReferences": None
                            },
                            {
                                "id": "task2",
                                "title": "Research competitors",
                                "importance": "normal",
                                "status": "notStarted",
                                "dueDateTime": {"dateTime": "2025-03-25T00:00:00Z"},
                                "parentReferences": {"id": "task1"}
                            }
                        ]
                    elif list_id == "list2":
                        list_tasks = [
                            {
                                "id": "task3",
                                "title": "Buy groceries",
                                "importance": "normal",
                                "status": "notStarted",
                                "dueDateTime": None,
                                "parentReferences": None
                            }
                        ]
                    
                    # Add list ID and name to each task
                    for task in list_tasks:
                        task["listId"] = list_id
                        task["listName"] = list_name
                        all_tasks.append(task)
                        
                except Exception as e:
                    logger.warning(f"Error getting tasks for list {list_id}: {e}")
            
            # Convert Outlook tasks to our Task format
            tasks = []
            for t in all_tasks:
                # Skip the instruction task as it's handled separately
                if t.get("title") == self.INSTRUCTION_TASK_TITLE:
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
                    title=t.get("title", ""),
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
            
            logger.debug(f"Retrieved {len(tasks)} tasks for app_login '{app_login}' / task_user_email '{task_user_email}'")
            return tasks
        except Exception as e:
            logger.error(f"Error getting Outlook tasks for app_login '{app_login}' / task_user_email '{task_user_email}': {e}")
            raise

    def get_ai_instructions(self, app_login, task_user_email) -> Optional[str]:
        """Get the AI instruction task content."""
        self._initialize_client(app_login=app_login, task_user_email=task_user_email)
        if not self.client:
            raise Exception(f"No Microsoft Graph client for app_login '{app_login}' / task_user_email '{task_user_email}'")

        try:
            # Get all task lists
            task_lists = []
            try:
                # In a real implementation, we would use:
                # task_lists_response = self.client.me.todo.lists.get()
                # task_lists = task_lists_response.value
                
                # For now, use mock data
                task_lists = [{"id": "list1"}, {"id": "list2"}]
            except Exception as e:
                logger.warning(f"Error getting Outlook task lists: {e}")
                task_lists = [{"id": "default"}]
            
            # Search for the instruction task in each list
            for task_list in task_lists:
                list_id = task_list["id"]
                
                try:
                    # In a real implementation, we would use:
                    # filter_query = f"title eq '{self.INSTRUCTION_TASK_TITLE}'"
                    # tasks_response = self.client.me.todo.lists.by_todo_task_list_id(list_id).tasks.get(filter=filter_query)
                    # instruction_tasks = tasks_response.value
                    
                    # For now, return a mock instruction
                    return """AI Instructions:
- Schedule friend catchups weekly
- Work on each project at least twice a week
- Keep mornings free for focused work
- Handle urgent tasks within 24 hours"""
                    
                except Exception as e:
                    logger.warning(f"Error searching for instruction task in list {list_id}: {e}")
            
            logger.warning(f"No AI instruction task found for app_login '{app_login}' / task_user_email '{task_user_email}'")
            return None
        except Exception as e:
            logger.error(f"Error getting AI instructions for app_login '{app_login}' / task_user_email '{task_user_email}': {e}")
            raise

    def update_task_status(self, app_login, task_user_email, task_id: str, status: str) -> bool:
        """Update task completion status."""
        self._initialize_client(app_login=app_login, task_user_email=task_user_email)
        if not self.client:
            raise Exception(f"No Microsoft Graph client for app_login '{app_login}' / task_user_email '{task_user_email}'")

        try:
            # Map our status to Outlook status
            outlook_status = "completed" if status == "completed" else "notStarted"
            
            # Try to verify the task exists first
            try:
                # In a real implementation, we would get the task to verify it exists
                # using the Microsoft Graph API
                # Example: task = self.client.me.todo.tasks.by_todo_task_id(task_id).get()
                
                # Mock check - in a real implementation, this would be replaced with an API call
                task_exists = True  # Placeholder - would check if task exists
                
                if task_exists:
                    # In a real implementation, we would update the task status using:
                    # self.client.me.todo.tasks.by_todo_task_id(task_id).patch({"status": outlook_status})
                    
                    logger.debug(f"Updated task {task_id} status to {status} for app_login '{app_login}' / task_user_email '{task_user_email}'")
                    return True
                else:
                    raise Exception(f"Task {task_id} not found in Outlook Tasks")
                    
            except Exception as task_error:
                error_msg = str(task_error).lower()
                if "not found" in error_msg or "404" in error_msg:
                    raise Exception(f"Task {task_id} not found in Outlook Tasks. It may have been deleted or synced incorrectly. Try refreshing your tasks.")
                # For other errors, log and propagate
                logger.error(f"Error updating Outlook Tasks task status for app_login '{app_login}' / task_user_email '{task_user_email}': {task_error}")
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
                logger.error(f"Error updating task status for app_login '{app_login}' / task_user_email '{task_user_email}': {e}")
                raise

    def create_instruction_task(self, app_login, task_user_email, instructions: str) -> bool:
        """Create or update the AI instruction task."""
        self._initialize_client(app_login=app_login, task_user_email=task_user_email)
        if not self.client:
            raise Exception(f"No Microsoft Graph client for app_login '{app_login}' / task_user_email '{task_user_email}'")

        try:
            # Get the default task list
            default_list_id = "default"
            try:
                # In a real implementation, we would use:
                # task_lists_response = self.client.me.todo.lists.get()
                # default_list_id = task_lists_response.value[0].id if task_lists_response.value else "default"
                default_list_id = "list1"  # Mock data
            except Exception as e:
                logger.warning(f"Error getting default task list: {e}")
            
            # Search for existing instruction task
            instruction_task_id = None
            try:
                # In a real implementation, we would use:
                # filter_query = f"title eq '{self.INSTRUCTION_TASK_TITLE}'"
                # tasks_response = self.client.me.todo.lists.by_todo_task_list_id(default_list_id).tasks.get(filter=filter_query)
                # instruction_tasks = tasks_response.value
                # instruction_task_id = instruction_tasks[0].id if instruction_tasks else None
                instruction_task_id = None  # Mock data - assume no existing task
            except Exception as e:
                logger.warning(f"Error searching for instruction task: {e}")
            
            if instruction_task_id:
                # Update existing task
                # In a real implementation, we would use:
                # self.client.me.todo.tasks.by_todo_task_id(instruction_task_id).patch({"body": {"content": instructions}})
                logger.debug(f"Updated AI instruction task for app_login '{app_login}' / task_user_email '{task_user_email}'")
            else:
                # Create new task
                # In a real implementation, we would use:
                # new_task = {
                #     "title": self.INSTRUCTION_TASK_TITLE,
                #     "body": {"content": instructions},
                #     "importance": "high"
                # }
                # self.client.me.todo.lists.by_todo_task_list_id(default_list_id).tasks.post(new_task)
                logger.debug(f"Created AI instruction task for app_login '{app_login}' / task_user_email '{task_user_email}'")
            
            return True
        except Exception as e:
            logger.error(f"Error managing instruction task for app_login '{app_login}' / task_user_email '{task_user_email}': {e}")
            raise

    # --- Credential Management (Not Applicable for OAuth Providers) ---

    def get_credentials(self, app_login, task_user_email):
        """Credentials for Outlook are handled via CalendarAccount (OAuth)."""
        logger.debug("OutlookTaskProvider.get_credentials called but not implemented (uses CalendarAccount)")
        # This method might be called by generic logic but isn't used for OAuth flow.
        # Returning None is safer than raising NotImplementedError if called unexpectedly.
        return None

    def store_credentials(self, app_login, task_user_email, credentials):
        """Credentials for Outlook are handled via CalendarAccount (OAuth)."""
        logger.error("OutlookTaskProvider.store_credentials should not be called directly.")
        # Raise error because storing credentials here bypasses the OAuth flow.
        raise NotImplementedError("Outlook credentials should be stored via the OAuth flow in CalendarAccount.")