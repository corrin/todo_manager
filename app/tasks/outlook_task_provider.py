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
        """Initialize the Microsoft Graph client using existing calendar credentials."""
        if self.client is None:
            account = CalendarAccount.get_by_email_provider_and_user(
                calendar_email=task_user_email,
                provider='o365',
                user_id=user_id
            )
            
            if not account or not account.token or account.needs_reauth:
                logger.warning(f"No valid Outlook account for user {user_id}")
                raise Exception("Outlook account needs authorization")
                
            try:
                credential = AccessTokenCredential(account.token)
                self.client = GraphServiceClient(credential)
                logger.debug(f"Initialized Microsoft Graph client for {user_id}")
            except Exception as e:
                logger.error(f"Failed to initialize Outlook client: {e}")
                if account:
                    account.needs_reauth = True
                    account.save()
                raise Exception("Outlook authentication failed")

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
        
        try:
            # Get all task lists
            try:
                task_lists = self.client.me.outlook.task_folders.get().value
                logger.debug(f"Retrieved {len(task_lists)} task lists for user {user_id}")
            except Exception as e:
                logger.error(f"Error getting task folders: {e}")
                raise Exception("Could not retrieve your task folders")
            
            # Get tasks from each list
            all_tasks = []
            for task_list in task_lists:
                list_id = task_list.id
                list_name = task_list.display_name
                
                try:
                    tasks = self.client.me.outlook.task_folders.by_id(list_id).tasks.get().value
                    
                    # Convert tasks to dict format and add list metadata
                    for task in tasks:
                        task_dict = task.to_dict()
                        task_dict["listId"] = list_id
                        task_dict["listName"] = list_name
                        all_tasks.append(task_dict)
                        
                except Exception as e:
                    logger.warning(f"Error getting tasks from folder {list_id}: {e}")
                    continue
            
            # Convert Outlook tasks to our Task format
            tasks = []
            for t in all_tasks:
                # Skip the instruction task as it's handled separately
                if t.get("subject") == self.INSTRUCTION_TASK_TITLE:
                    continue
                
                # Convert due date from ISO format
                due_date = None
                if t.get("dueDateTime"):
                    try:
                        due_date_str = t["dueDateTime"].get("dateTime")
                        if due_date_str:
                            due_date = datetime.fromisoformat(due_date_str.replace("Z", "+00:00"))
                    except ValueError as e:
                        logger.warning(f"Could not parse due date for task: {e}")

                # Simplify priority mapping
                priority = {
                    "low": 1,
                    "normal": 2,
                    "high": 3,
                    "urgent": 4
                }.get(t.get("importance", "normal"), 2)

                # Simplify status mapping
                status = "completed" if t.get("status") == "completed" else "active"

                task = Task(
                    id=t["id"],
                    title=t.get("subject", ""),
                    project_id=t.get("listId", ""),
                    priority=priority,
                    due_date=due_date,
                    status=status,
                    is_instruction=False,
                    parent_id=t.get("parentReferences", {}).get("id"),
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

    def update_task(self, user_id, task_id, task_data=None) -> bool:
        """Update task properties in Outlook.
        
        Args:
            user_id: The user's database ID
            task_id: The task's primary key
            task_data: Dictionary containing fields to update
            
        Returns:
            bool: True if update was successful, False otherwise
        """
        if not task_data:
            return True  # No updates needed

        try:
            # Get the task from our database
            task = Task.query.filter_by(id=task_id, user_id=user_id).first()
            if not task:
                logger.error(f"Task {task_id} not found for user {user_id}")
                return False

            # Initialize client with task's user email
            self._initialize_client(user_id=user_id, task_user_email=task.task_user_email)
            
            # Prepare update payload
            update_args = {}
            
            if 'title' in task_data:
                update_args['subject'] = task_data['title']
                
            if 'due_date' in task_data:
                update_args['dueDateTime'] = {
                    'dateTime': task_data['due_date'].isoformat(),
                    'timeZone': 'UTC'
                } if task_data['due_date'] else None
            
            if 'priority' in task_data:
                update_args['importance'] = {
                    1: 'low',
                    2: 'normal',
                    3: 'high',
                    4: 'urgent'
                }.get(task_data['priority'], 'normal')
            
            if 'status' in task_data:
                update_args['status'] = 'completed' if task_data['status'] == 'completed' else 'notStarted'

            # Only proceed if we have updates
            if not update_args:
                return True

            # Execute the update
            self.client.me.outlook.tasks.by_id(task.provider_task_id).patch(update_args)
            logger.info(f"Updated Outlook task {task_id} with: {update_args.keys()}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update Outlook task {task_id}: {e}")
            return False

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
        """Create or update the AI instruction task in Outlook."""
        self._initialize_client(user_id=user_id, task_user_email=task_user_email)

        try:
            # Get default task folder
            task_folders = self.client.me.outlook.task_folders.get().value
            if not task_folders:
                raise Exception("No task folders found")
            default_folder_id = task_folders[0].id

            # Check for existing instruction task
            existing_task = None
            try:
                tasks = self.client.me.outlook.task_folders.by_id(default_folder_id).tasks.filter(
                    f"subject eq '{self.INSTRUCTION_TASK_TITLE}'"
                ).get().value
                if tasks:
                    existing_task = tasks[0]
            except Exception as e:
                logger.warning(f"Error checking for existing instruction task: {e}")

            if existing_task:
                # Update existing task
                existing_task.body.content = instructions
                existing_task.patch()
                logger.debug(f"Updated instruction task for {user_id}")
            else:
                # Create new task
                new_task = {
                    "subject": self.INSTRUCTION_TASK_TITLE,
                    "body": {"content": instructions, "contentType": "text"},
                    "importance": "high"
                }
                self.client.me.outlook.task_folders.by_id(default_folder_id).tasks.post(new_task)
                logger.debug(f"Created new instruction task for {user_id}")

            return True
            
        except Exception as e:
            logger.error(f"Failed to manage instruction task for {user_id}: {e}")
            raise Exception(f"Could not update instruction task: {e}")

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