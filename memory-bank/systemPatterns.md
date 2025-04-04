# System Architecture and Patterns

## Core Architecture

The Task Master application is structured around five main components:

1. **Task Management** - Creating, updating, and tracking tasks across various providers
2. **AI Processing** - Natural language processing for task creation and management
3. **Calendar Management** - Syncing and managing events from multiple calendar sources
4. **Authentication** - User authentication and provider credential management
5. **Database** - Data persistence and relationship management

## Key Patterns

### Provider Pattern

All service integrations follow the provider pattern with these common characteristics:

#### AIProvider Interface
```python
class AIProvider(ABC):
    @abstractmethod
    def needs_auth(self) -> bool:
        pass
        
    @abstractmethod
    def authenticate(self, credentials: dict) -> bool:
        pass
        
    @abstractmethod
    def generate_completion(self, prompt: str, **kwargs) -> str:
        pass
        
    @abstractmethod
    def get_credentials(self) -> dict:
        pass
```

#### TaskProvider Interface
```python
class TaskProvider(ABC):
    @abstractmethod
    def _get_provider_name(self) -> str:
        """Return the name of this provider (e.g., 'todoist')"""
        pass
        
    def get_credentials(self, email):
        """Get task provider credentials for the user."""
        pass
        
    def store_credentials(self, email, credentials):
        """Store task provider credentials for the user."""
        pass

    @abstractmethod
    def authenticate(self, email):
        """Authenticate with the task provider."""
        pass

    @abstractmethod
    def get_tasks(self, email) -> List[Task]:
        """Get all tasks for the user."""
        pass

    @abstractmethod
    def get_ai_instructions(self, email) -> Optional[str]:
        """Get the AI instruction task content."""
        pass

    @abstractmethod
    def update_task_status(self, email, task_id: str, status: str) -> bool:
        """Update task completion status."""
        pass
        
    @abstractmethod
    def create_instruction_task(self, email, instructions: str) -> bool:
        """Create or update an AI instruction task."""
        pass
```

#### CalendarProvider Interface
```python
class CalendarProvider(ABC):
    @abstractmethod
    def needs_auth(self) -> bool:
        pass
        
    @abstractmethod
    def authenticate(self, credentials: dict) -> bool:
        pass
        
    @abstractmethod
    def get_events(self, start_time: datetime, end_time: datetime) -> List[Event]:
        pass
        
    @abstractmethod
    def create_event(self, event: Event) -> bool:
        pass
        
    @abstractmethod
    def update_event(self, event: Event) -> bool:
        pass
        
    @abstractmethod
    def delete_event(self, event_id: str) -> bool:
        pass
        
    @abstractmethod
    def get_credentials(self) -> dict:
        pass
        
    @abstractmethod
    def requires_reauth(self) -> bool:
        pass
```

#### AuthProvider Interface
```python
class AuthProvider(ABC):
    @abstractmethod
    def authenticate(self, request: Request) -> User:
        pass
        
    @abstractmethod
    def logout(self, request: Request) -> bool:
        pass
        
    @abstractmethod
    def get_current_user(self, request: Request) -> User:
        pass
```

### Factory Pattern

Provider factories manage creation of specific provider instances:

```python
class CalendarProviderFactory:
    @staticmethod
    def create_provider(provider_type: str, **kwargs) -> CalendarProvider:
        if provider_type == "google":
            return GoogleCalendarProvider(**kwargs)
        elif provider_type == "office365":
            return O365CalendarProvider(**kwargs)
        else:
            raise ValueError(f"Unknown provider type: {provider_type}")
```

### Manager Pattern

Managers coordinate between multiple providers and handle selection logic:

```python
class TaskManager:
    def __init__(self):
        self.providers = {}
        self.provider_classes = {
            "todoist": TodoistProvider,
            "sqlite": SQLiteTaskProvider,
            "outlook": OutlookTaskProvider,
            "google_tasks": GoogleTaskProvider,
        }
        self._initialize_providers()
        
    def _initialize_providers(self):
        """Initialize available task providers."""
        for provider_name, provider_class in self.provider_classes.items():
            try:
                self.providers[provider_name] = provider_class()
                logger.debug(f"Initialized {provider_name} provider")
            except Exception as e:
                logger.error(f"Failed to initialize {provider_name} provider: {e}")
                
    def authenticate(self, email, provider_name=None):
        """Authenticate with specified or all providers."""
        pass
        
    def get_tasks(self, email, provider_name=None):
        """Get tasks from specified or default provider."""
        pass
        
    def get_ai_instructions(self, email, provider_name=None):
        """Get AI instructions from specified or default provider."""
        pass
        
    def update_task_status(self, email, task_id, status, provider_name=None):
        """Update task status in specified or default provider."""
        pass
        
    def create_instruction_task(self, email, instructions, provider_name=None):
        """Create or update the AI instruction task."""
        pass
```

### Database Architecture

#### Database Singleton
- Database configuration managed through a central Database class
- SQLAlchemy ORM integration
- Connection management through application context

#### Core Models
- **User**: Authentication information, relationships to accounts and tasks
- **CalendarAccount**: Provider-specific calendar accounts with credentials
- **Task**: Task details with relationships to users and due dates

#### Data Isolation
- All queries filter by user_id for data isolation
- No cross-user data access in standard routes
- Session management tied to authenticated user

#### Migration System
- Alembic/Flask-Migrate for schema evolution
- Version-controlled database schema
- Upgrade/downgrade paths maintained

### User Management

#### Current Approach
Two competing systems currently exist:
1. **File-based**: User data stored in JSON files in user-specific directories
2. **Database-based**: User data stored in SQL database with ORM models

#### Authentication Flow
1. User authenticates with Google Identity Services
2. Server verifies JWT token
3. User record created or retrieved
4. Session established with Flask-Login

### Calendar Integration Architecture

#### Provider Design
- Abstract `CalendarProvider` interface defines the contract
- Concrete implementations for Google Calendar and Office 365
- Factory pattern for provider instantiation
- Consistent error handling and token refresh mechanism

#### OAuth Flow
1. **Initiation**: User requests to connect a calendar account
2. **Redirect**: Application redirects to provider's OAuth consent screen
3. **Authorization**: User grants permissions to the application
4. **Callback**: Provider redirects back with authorization code
5. **Token Exchange**: Application exchanges code for access/refresh tokens
6. **Storage**: Tokens stored in database with the CalendarAccount
7. **Verification**: Test API call to confirm successful authentication

#### Token Management
- Refresh tokens stored securely in the database
- Automatic token refresh when expired
- Error handling for invalid/revoked tokens
- Reauthorization flow for permanently invalid tokens

#### Calendar Synchronization
- Periodic/on-demand calendar synchronization
- Async processing for O365 API calls
- Proper error handling for network/API issues
- User feedback for sync status

#### Calendar Event Handling
- Consistent event representation across providers
- Time zone handling (with some known issues)
- CRUD operations for all event types
- Conflict detection for overlapping events

### Task System Architecture

#### Task Data Model
```python
@dataclass
class Task:
    """Represents a task from any task provider."""
    id: str
    title: str
    project_id: str
    priority: int
    due_date: Optional[datetime]
    status: str
    is_instruction: bool = False
    parent_id: Optional[str] = None
    section_id: Optional[str] = None
    project_name: Optional[str] = None
```

#### Provider-Specific Implementations

1. **Todoist Provider**
   - Uses Todoist API Python client
   - API key-based authentication
   - Project mapping for task organization
   - Instruction task support with special handling
   - Error handling for API failures

2. **SQLite Provider**
   - Local SQLite database in user folder
   - JSON serialization for task data
   - Simple file-based authentication check
   - Instruction task support through special task type
   - Database initialization and schema management

3. **Outlook Tasks Provider**
   - Leverages Microsoft Graph API
   - Reuses O365 calendar authentication
   - Token management through calendar account
   - Task operations via Microsoft To-Do API
   - Placeholder implementation with minimal functionality

4. **Google Tasks Provider**
   - Uses Google Tasks API
   - Reuses Google calendar authentication
   - Token management through calendar account
   - Task operations via Google Tasks API
   - Placeholder implementation with minimal functionality

#### Credential Management

- **File-Based Storage**: Credentials stored in JSON files in user directories
- **Database Storage**: Calendar accounts stored in database with tokens
- **Cross-Provider Reuse**: Calendar credentials reused for task providers
- **Calendar-to-Task Mapping**: Automatic mapping of calendar providers to corresponding task providers

#### Task Synchronization

```python
def sync_tasks(app_login):
    """Sync tasks from all connected task providers."""
    results = {
        'success': [],
        'errors': [],
        'needs_reauth': [],
        'status': 'success',
        'message': ''
    }
    
    # Get all task accounts for the user
    accounts = get_task_accounts(app_login)
    
    for account in accounts:
        provider_name = account['provider']
        task_user_email = account['task_user_email']
        
        # Handle synchronization for each account
        try:
            # Check authentication
            # Fetch tasks
            # Process results
        except Exception:
            # Handle errors
            pass
    
    return results
```

#### Task Hierarchy

- Task organization into projects and sections
- Parent-child relationships between tasks
- Priority-based ordering
- Due date sorting and grouping
- Special handling for instruction tasks

### Asynchronous Operations

#### Async Calendar Operations
- O365 calendar operations implemented asynchronously
- Background token refresh for expired credentials
- Error handling with graceful fallbacks

#### Batch Processing
- Calendar synchronization processes multiple accounts in sequence
- Error isolation between accounts (one failure doesn't stop others)
- Result aggregation for user feedback 