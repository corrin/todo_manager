# Task Provider Architecture

## Core Components

### 1. TaskProvider Interface
```python
class TaskProvider(ABC):
    def _get_provider_name(self) -> str:
        """Return provider name (e.g., 'todoist')"""
        pass

    def authenticate(self, email):
        """Check/refresh credentials, return auth URL if needed"""
        pass

    def get_tasks(self, email):
        """Get all tasks for user"""
        pass

    def get_ai_instructions(self, email):
        """Get the AI instruction task content"""
        pass

    def update_task_status(self, email, task_id, status):
        """Update task completion status"""
        pass
```

### 2. TodoistProvider Implementation
- Implements TaskProvider interface
- Handles Todoist API interactions
- Manages user-specific credentials
- Finds and reads AI instruction task

### 3. TaskManager
- Manages task provider instances
- Handles provider selection
- Coordinates task operations
- Manages authentication flow

## AI Instruction Task

### Format
- Single special task in Todoist
- Contains all AI instructions
- Free-form natural language
- Examples:
  ```
  "AI Instructions:
   - Schedule friend catchups weekly
   - Work on each project at least twice a week
   - Keep mornings free for focused work
   - Handle urgent tasks within 24 hours"
  ```

### Benefits
- Single source of truth
- Natural language instructions
- Easy to update
- Flexible and extensible

## Authentication Flow

1. **Initial Check**
   - TaskManager checks for credentials
   - Redirects to setup if needed
   - Validates existing credentials

2. **Credential Setup**
   - Web interface for API token
   - Secure token storage
   - Validation with Todoist API

3. **Ongoing Management**
   - Regular credential validation
   - Error handling for API issues
   - Token refresh if needed

## Data Structures

### Task Format
```python
@dataclass
class Task:
    id: str
    title: str
    project_id: str
    priority: int
    due_date: Optional[datetime]
    status: str
    is_instruction: bool  # True only for AI instruction task
```

## Implementation Phases

### Phase 1: Core Structure
1. Create TaskProvider interface
2. Implement basic TodoistProvider
3. Create TaskManager
4. Add credential management

### Phase 2: AI Integration
1. Implement instruction task detection
2. Add instruction parsing
3. Connect with AI system
4. Test instruction processing

### Phase 3: Integration
1. Add calendar integration
2. Implement status updates
3. Add error handling
4. Create user interface

## Key Features

### 1. Task Management
- CRUD operations for tasks
- Status updates
- Priority handling
- Project organization

### 2. AI Instructions
- Single instruction task
- Natural language processing
- Flexible scheduling rules
- Easy updates

### 3. Integration Points
- AI system interface
- Calendar system interface
- User interface components
- Authentication flow

## Security Considerations

### 1. Credential Storage
- User-specific storage
- Secure token handling
- Access control
- Token validation

### 2. API Security
- Rate limiting
- Error handling
- Token refresh
- Request validation

### 3. Data Protection
- User data isolation
- Secure storage
- Access logging
- Error tracking

## Next Steps

1. **Implementation**
   - Create base interfaces
   - Implement Todoist provider
   - Add credential management
   - Create task manager

2. **Testing**
   - Unit tests for components
   - Integration tests
   - Security testing
   - Performance testing

3. **Documentation**
   - API documentation
   - Setup instructions
   - Usage examples
   - Error handling guide

This design simplifies the rule system by using a single AI instruction task, making the system more flexible and easier to manage while maintaining our provider-based architecture.