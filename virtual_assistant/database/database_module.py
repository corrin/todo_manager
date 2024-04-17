from abc import ABC, abstractmethod


class DatabaseInterface(ABC):
    @abstractmethod
    def create_task(self, task_data):
        """Create a task based on provided task data"""
        pass

    @abstractmethod
    def get_tasks(self):
        """Retrieve tasks from the database"""
        pass
