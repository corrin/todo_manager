from .task_module import TaskInterface


class TodoistModule(TaskInterface):
    def create_task(self, task_data):
        # Todoist-specific implementation for creating a task
        pass

    def get_tasks(self):
        # Todoist-specific implementation for retrieving tasks
        pass

    # Other Todoist-specific methods
