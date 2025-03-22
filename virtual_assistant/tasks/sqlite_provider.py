import sqlite3
import json
import os
from datetime import datetime
from typing import List, Optional
from flask import redirect, url_for

from .task_provider import TaskProvider, Task
from virtual_assistant.utils.logger import logger
import uuid
from virtual_assistant.utils.user_manager import UserManager


class SQLiteTaskProvider(TaskProvider):
    """SQLite-based implementation of the task provider interface."""

    INSTRUCTION_TASK_TITLE = "AI Instructions"
    DB_FILENAME = "tasks.db"

    def __init__(self):
        super().__init__()
        self.db_path = None

    def _get_provider_name(self) -> str:
        return "sqlite"

    def _get_db_path(self, email: str) -> str:
        """Get path to user's SQLite database."""
        user_folder = UserManager.get_user_folder()
        return os.path.join(user_folder, self.DB_FILENAME)

    def _init_db(self, email: str):
        """Initialize SQLite database with tasks table."""
        db_path = self._get_db_path(email)
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        with sqlite3.connect(db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    email TEXT NOT NULL,
                    data JSON NOT NULL
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_email ON tasks (email)")
            conn.commit()

    def authenticate(self, email):
        """Check if we can access the SQLite database."""
        db_path = self._get_db_path(email)
        if not os.path.exists(db_path):
            logger.info(f"SQLite database not found for {email}, redirecting to setup")
            return self.provider_name, redirect(url_for('sqlite_auth.setup_storage'))
        
        logger.debug(f"SQLite database verified for {email}")
        return None

    def get_tasks(self, email) -> List[Task]:
        """Get all tasks from SQLite storage."""
        try:
            db_path = self._get_db_path(email)
            tasks = []
            
            with sqlite3.connect(db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    "SELECT data FROM tasks WHERE email = ?",
                    (email,)
                )
                for row in cursor:
                    task_data = json.loads(row['data'])
                    
                    # Convert stored task to Task object
                    due_date = None
                    if task_data.get('due_date'):
                        due_date = datetime.fromisoformat(task_data['due_date'])

                    task = Task(
                        id=task_data['id'],
                        title=task_data['title'],
                        project_id=task_data.get('project_id', ''),
                        priority=task_data.get('priority', 1),
                        due_date=due_date,
                        status=task_data.get('status', 'active'),
                        is_instruction=False
                    )
                    tasks.append(task)
            
            logger.debug(f"Retrieved {len(tasks)} tasks for {email}")
            return tasks
        except Exception as e:
            logger.error(f"Error getting tasks from SQLite: {e}")
            raise

    def get_ai_instructions(self, email) -> Optional[str]:
        """Get the AI instruction task content."""
        try:
            db_path = self._get_db_path(email)
            
            with sqlite3.connect(db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    "SELECT data FROM tasks WHERE email = ? AND json_extract(data, '$.title') = ?",
                    (email, self.INSTRUCTION_TASK_TITLE)
                )
                row = cursor.fetchone()
                
                if row:
                    task_data = json.loads(row['data'])
                    logger.debug(f"Found AI instruction task for {email}")
                    return task_data.get('description', '')
                else:
                    logger.warning(f"No AI instruction task found for {email}")
                    return None
        except Exception as e:
            logger.error(f"Error getting AI instructions from SQLite: {e}")
            raise

    def update_task_status(self, email, task_id: str, status: str) -> bool:
        """Update task completion status."""
        try:
            db_path = self._get_db_path(email)
            
            with sqlite3.connect(db_path) as conn:
                # Check if task exists
                cursor = conn.execute(
                    "SELECT data FROM tasks WHERE id = ? AND email = ?",
                    (task_id, email)
                )
                row = cursor.fetchone()
                
                if row:
                    # Parse task data
                    task_data = json.loads(row[0])
                    
                    # Check if status is already the requested value
                    current_status = task_data.get('status', 'active')
                    if current_status == status:
                        logger.debug(f"Task {task_id} already has status {status}, no update needed")
                        return True
                    
                    # Update status
                    task_data['status'] = status
                    
                    # Update task
                    conn.execute(
                        "UPDATE tasks SET data = ? WHERE id = ?",
                        (json.dumps(task_data), task_id)
                    )
                    conn.commit()
                    
                    logger.debug(f"Updated task {task_id} status to {status}")
                    return True
                else:
                    # Task not found
                    error_msg = f"Task {task_id} not found in SQLite database for {email}"
                    logger.warning(error_msg)
                    raise Exception(error_msg)
                    
        except sqlite3.Error as e:
            error_msg = str(e)
            logger.error(f"SQLite database error: {error_msg}")
            raise Exception(f"Database error: {error_msg}")
            
        except json.JSONDecodeError as e:
            error_msg = str(e)
            logger.error(f"Error parsing task data: {error_msg}")
            raise Exception(f"Error reading task data: {error_msg}")
            
        except Exception as e:
            logger.error(f"Error updating task status in SQLite: {e}")
            raise

    def create_instruction_task(self, email, instructions: str) -> bool:
        """Create or update the AI instruction task."""
        try:
            db_path = self._get_db_path(email)
            
            with sqlite3.connect(db_path) as conn:
                # Check if instruction task exists
                cursor = conn.execute(
                    "SELECT id FROM tasks WHERE email = ? AND json_extract(data, '$.title') = ?",
                    (email, self.INSTRUCTION_TASK_TITLE)
                )
                row = cursor.fetchone()
                
                task_data = {
                    'id': 'instruction',
                    'title': self.INSTRUCTION_TASK_TITLE,
                    'description': instructions,
                    'status': 'active'
                }
                
                if row:
                    # Update existing task
                    conn.execute(
                        "UPDATE tasks SET data = ? WHERE id = ?",
                        (json.dumps(task_data), 'instruction')
                    )
                    logger.debug(f"Updated AI instruction task for {email}")
                else:
                    # Create new task
                    conn.execute(
                        "INSERT INTO tasks (id, email, data) VALUES (?, ?, ?)",
                        ('instruction', email, json.dumps(task_data))
                    )
                    logger.debug(f"Created AI instruction task for {email}")
                
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Error managing instruction task in SQLite: {e}")
            raise

    def create_task(self, email: str, title: str, description: str) -> bool:
        """Create a new task in SQLite."""
        try:
            db_path = self._get_db_path(email)
            
            with sqlite3.connect(db_path) as conn:
                task_id = str(uuid.uuid4())
                task_data = {
                    'id': task_id,
                    'title': title,
                    'description': description,
                    'status': 'active'
                }
                
                conn.execute(
                    "INSERT INTO tasks (id, email, data) VALUES (?, ?, ?)",
                    (task_id, email, json.dumps(task_data))
                )
                conn.commit()
                logger.debug(f"Created new task {task_id} for {email}")
                return True
        except Exception as e:
            logger.error(f"Error creating task in SQLite: {e}")
            raise