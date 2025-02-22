# Todo Manager Architecture

## System Overview

The system follows a provider-based architecture with three main components:

### 1. Task Management (Source)
- Todoist as the source system for tasks
- Tasks represent work items
- Single AI instruction task defines scheduling behavior
- Provider pattern for potential future task sources

### 2. AI Processing (Rules Engine)
- Multiple AI provider support (OpenAI, Grok, Gemini, Claude, etc.)
- Provider-based architecture for AI services
- Each provider implements common interface
- Automatic fallback between providers
- User-specific credentials per provider
- Natural language instruction processing

### 3. Calendar Management (Output)
- Multiple calendar provider support
- Provider-based architecture (Google, O365)
- 30-minute block allocation
- Fixed appointment handling

## Provider Pattern

All external services follow a consistent provider pattern:

### Provider Interface
- Common interface for each service type
- Standard authentication methods
- Consistent credential management
- Error handling patterns

### Credential Management
- User-specific credentials
- Secure storage in user folders
- Provider-specific authentication flows
- Credential refresh handling

### Manager Layer
- Manages multiple providers
- Handles provider selection
- Implements fallback logic
- Coordinates authentication

## Task Provider Architecture

### TaskProvider Interface
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

### TodoistProvider Implementation
- Implements TaskProvider interface
- Handles Todoist API interactions
- Manages user-specific credentials
- Finds and reads AI instruction task

### TaskManager
- Manages task provider instances
- Handles provider selection
- Coordinates task operations
- Manages authentication flow

## Authentication Flow

### 1. System Authentication
- User authenticates via Google
- Creates user-specific secure storage
- System checks for credentials
- Redirects to setup if needed
- Validates existing credentials

### 2. Provider Authentication
- Each provider checks credentials
- Missing credentials trigger setup
- Credentials stored per user
- Regular validation checks

### 3. Credential Management
- Secure credential storage
- Provider-specific formats
- Automatic refresh where supported
- Clear error handling

## Implementation Structure

### AI Layer
- AIProvider interface
- Provider implementations (OpenAI, Grok, Gemini, Claude)
- AIManager for coordination
- Provider-specific auth flows

### Calendar Layer
- CalendarProvider interface
- Provider implementations (Google, O365)
- Calendar coordination
- OAuth handling

### Task Layer
- TaskProvider interface
- Todoist implementation
- AI instruction management
- Status tracking

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

## Module Organization

The codebase is organized into separate modules for each layer:

### Database Module
- Handles interactions with task sources
- Abstract base classes for common operations
- Concrete implementations per provider
- CRUD operations for tasks

### AI Module
- Handles integration with AI services
- Abstract interface for AI operations
- Concrete implementations per provider
- Text generation and analysis

### Calendar Module
- Handles calendar integrations
- Abstract interface for calendar operations
- Concrete implementations per provider
- Event management and scheduling

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

The architecture emphasizes:
- Clean separation of concerns
- Consistent patterns across services
- User-specific credential management
- Extensibility for new providers
- Simple, natural language configuration
- Modular and maintainable design
- Factory pattern for provider instantiation
- Dependency injection for flexible configuration