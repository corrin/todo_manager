from utils.user_manager import UserManager
from database.todoist_module import TodoistModule
from utils.logger import logger


def test_todoist_connection():
    """Test the Todoist connection and basic functionality."""
    
    # Set a test user
    UserManager.set_current_user("lakeland@gmail.com")
    
    # Check if we have a token
    token = UserManager.get_todoist_token()
    if not token:
        print("\nNo Todoist token found!")
        print("Please set your token first using:")
        print("python set_todoist_token.py YOUR_API_TOKEN\n")
        return
    
    # Initialize Todoist module
    todoist = TodoistModule()
    
    # Test projects
    print("\nFetching projects...")
    projects = todoist.get_projects()
    if projects:
        print(f"Found {len(projects)} projects:")
        for project in projects:
            print(f"- {project.name}")
    else:
        print("No projects found or error occurred")
    
    # Test tasks
    print("\nFetching tasks...")
    tasks = todoist.get_tasks()
    if tasks:
        print(f"Found {len(tasks)} tasks:")
        for task in tasks[:5]:  # Show first 5 tasks only
            print(f"- {task.content}")
        if len(tasks) > 5:
            print(f"... and {len(tasks) - 5} more")
    else:
        print("No tasks found or error occurred")
    
    # Test rules
    print("\nFetching rules...")
    rules = todoist.get_rules()
    if rules:
        print(f"Found {len(rules)} rules:")
        for rule in rules:
            print(f"- {rule.content}")
    else:
        print("No rules found or error occurred")


if __name__ == "__main__":
    test_todoist_connection()