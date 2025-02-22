import json
import os
from datetime import datetime
from typing import List, Optional
from flask import redirect, url_for

from .task_provider import TaskProvider, Task
from virtual_assistant.utils.logger import logger


class JsonTaskProvider(TaskProvider):
    """JSON file-based implementation of the task provider interface."""

    INSTRUCTION_TASK_TITLE = "AI Instructions"
    TASKS_FILENAME = "tasks.json"

    def __init__(self):
        super().__init__()
        self.tasks_file = None

    def _get_provider_name(self) -> str:
        return "json"

    def _get_tasks_file(self, email: str) -> str:
        """Get path to user's tasks file."""
        user_folder = self.get_user_folder(email)
        return os.path.join(user_folder, self.TASKS_FILENAME)

    def _load_tasks(self, email: str) -> List[dict]:
        """Load tasks from JSON file."""
        tasks_file = self._get_tasks_file(email)
        if os.path.exists(tasks_file):
            with open(tasks_file, 'r') as f:
                return json.load(f)
        return []

    def _save_tasks(self, email: str, tasks: List[dict]):
        """Save tasks to JSON file."""
        tasks_file = self._get_tasks_file(email)
        os.makedirs(os.path.dirname(tasks_file), exist_ok=True)
        with open(tasks_file, 'w') as f:
            json.dump(tasks, f, indent=2)

    def authenticate(self, email):
        """Check if we have a tasks file and can read/write it."""
        tasks_file = self._get_tasks_file(email)
        
        try:
            # Try to read/write the tasks file
            if not os.path.exists(tasks_file):
                self._save_tasks(email, [])
            else:
                self._load_tasks(email)
            logger.debug(f"JSON tasks file verified for {email}")
            return None
        except Exception as e:
            logger.error(f"Error accessing JSON tasks file for {email}: {e}")
            return self.provider_name, redirect(url_for('json_auth.setup_storage'))

    def get_tasks(self, email) -> List[Task]:
        """Get all tasks from JSON storage."""
        try:
            tasks_data = self._load_tasks(email)
            tasks = []
            for t in tasks_data:
                # Skip the instruction task
                if t['title'] == self.INSTRUCTION_TASK_TITLE:
                    continue
                
                # Convert stored task to Task object
                due_date = None
                if t.get('due_date'):
                    due_date = datetime.fromisoformat(t['due_date'])

                task = Task(
                    id=t['id'],
                    title=t['title'],
                    project_id=t.get('project_id', ''),
                    priority=t.get('priority', 1),
                    due_date=due_date,
                    status=t.get('status', 'active'),
                    is_instruction=False
                )
                tasks.append(task)
            
            logger.debug(f"Retrieved {len(tasks)} tasks for {email}")
            return tasks
        except Exception as e:
            logger.error(f"Error getting tasks from JSON: {e}")
            raise

    def get_ai_instructions(self, email) -> Optional[str]:
        """Get the AI instruction task content."""
        try:
            tasks_data = self._load_tasks(email)
            instruction_task = next(
                (t for t in tasks_data if t['title'] == self.INSTRUCTION_TASK_TITLE),
                None
            )
            
            if instruction_task:
                logger.debug(f"Found AI instruction task for {email}")
                return instruction_task.get('description', '')
            else:
                logger.warning(f"No AI instruction task found for {email}")
                return None
        except Exception as e:
            logger.error(f"Error getting AI instructions from JSON: {e}")
            raise

    def update_task_status(self, email, task_id: str, status: str) -> bool:
        """Update task completion status."""
        try:
            tasks_data = self._load_tasks(email)
            task = next((t for t in tasks_data if t['id'] == task_id), None)
            
            if task:
                task['status'] = status
                self._save_tasks(email, tasks_data)
                logger.debug(f"Updated task {task_id} status to {status}")
                return True
            else:
                logger.warning(f"Task {task_id} not found")
                return False
        except Exception as e:
            logger.error(f"Error updating task status in JSON: {e}")
            raise

    def create_instruction_task(self, email, instructions: str) -> bool:
        """Create or update the AI instruction task."""
        try:
            tasks_data = self._load_tasks(email)
            instruction_task = next(
                (t for t in tasks_data if t['title'] == self.INSTRUCTION_TASK_TITLE),
                None
            )
            
            if instruction_task:
                # Update existing task
                instruction_task['description'] = instructions
                logger.debug(f"Updated AI instruction task for {email}")
            else:
                # Create new task
                tasks_data.append({
                    'id': 'instruction',
                    'title': self.INSTRUCTION_TASK_TITLE,
                    'description': instructions,
                    'status': 'active'
                })
                logger.debug(f"Created AI instruction task for {email}")
            
            self._save_tasks(email, tasks_data)
            return True
        except Exception as e:
            logger.error(f"Error managing instruction task in JSON: {e}")
            raise