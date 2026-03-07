"""
Task hierarchy module for handling hierarchical task structures.
"""
from typing import Dict, List, Optional, Set
from .task_provider import Task


class TaskHierarchy:
    """
    Handles the hierarchical structure of tasks.
    
    This class is responsible for:
    1. Building a hierarchical representation of tasks
    2. Flattening the hierarchy into a format suitable for display
    3. Providing methods to access and manipulate the hierarchy
    """
    
    def __init__(self, tasks: List[Task]):
        """
        Initialize the task hierarchy with a list of tasks.
        
        Args:
            tasks: List of Task objects
        """
        self.tasks = tasks
        self.tasks_by_id = {task.id: task for task in tasks}
        self.project_names = self._get_project_names()
        self.children_map = self._build_children_map()
        
    def _get_project_names(self) -> Dict[str, str]:
        """
        Get a mapping of project IDs to project names.
        
        Returns:
            Dict mapping project IDs to project names
        """
        project_names = {}
        for task in self.tasks:
            if task.project_id and task.project_name:
                project_names[task.project_id] = task.project_name
        return project_names
    
    def _build_children_map(self) -> Dict[str, List[str]]:
        """
        Build a mapping of parent task IDs to lists of child task IDs.
        
        Returns:
            Dict mapping parent task IDs to lists of child task IDs
        """
        children_map = {}
        for task in self.tasks:
            if task.parent_id:
                if task.parent_id not in children_map:
                    children_map[task.parent_id] = []
                children_map[task.parent_id].append(task.id)
        return children_map
    
    def get_root_tasks(self) -> List[Task]:
        """
        Get all root tasks (tasks with no parent).
        
        Returns:
            List of root Task objects
        """
        return [task for task in self.tasks if not task.parent_id]
    
    def get_children(self, task_id: str) -> List[Task]:
        """
        Get all children of a task.
        
        Args:
            task_id: ID of the parent task
            
        Returns:
            List of child Task objects
        """
        if task_id not in self.children_map:
            return []
        return [self.tasks_by_id[child_id] for child_id in self.children_map[task_id]]
    
    def get_task_path(self, task_id: str) -> List[Task]:
        """
        Get the path from the root to a task.
        
        Args:
            task_id: ID of the task
            
        Returns:
            List of Task objects representing the path from root to task
        """
        path = []
        current_task = self.tasks_by_id.get(task_id)
        
        while current_task:
            path.insert(0, current_task)
            if not current_task.parent_id:
                break
            current_task = self.tasks_by_id.get(current_task.parent_id)
            
        return path
    
    def get_task_path_string(self, task_id: str, separator: str = " > ") -> str:
        """
        Get a string representation of the path from root to a task.
        
        Args:
            task_id: ID of the task
            separator: Separator to use between task titles
            
        Returns:
            String representation of the path
        """
        path = self.get_task_path(task_id)
        return separator.join(task.title for task in path)
    
    def get_flattened_tasks(self) -> List[Dict]:
        """
        Get a flattened list of tasks with their full paths.
        
        Returns:
            List of dicts with task and path information
        """
        flattened = []
        
        for task in self.tasks:
            path_string = self.get_task_path_string(task.id)
            project_name = self.project_names.get(task.project_id, "")
            
            # Create the flattened_name by combining project and path information
            parts = []
            if project_name:
                parts.append(f"[{project_name}]")
                
            # If path contains more than just the task name, add the path
            if path_string and path_string != task.title:
                parts.append(path_string)
            else:
                parts.append(task.title)
                
            flattened_name = " > ".join(parts)
            
            flattened.append({
                "task": task,
                "path": path_string,
                "project": project_name,
                "flattened_name": flattened_name
            })
            
        return flattened