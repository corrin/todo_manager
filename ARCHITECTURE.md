# Todo Manager Architecture

## System Overview

The system is built on Flask and follows a provider-based architecture with three main components:

### 1. Task Management (Source)
- Todoist as the primary task source with SQLite alternative
- Single AI instruction task defines scheduling behavior
- `TaskProvider` interface with factory pattern implementation
- Tasks represent work items with standardized data structure

### 2. AI Processing (Rules Engine)
- Multiple AI provider support (OpenAI, Grok)
- Each provider implements the `AIProvider` interface
- Automatic fallback between providers when one fails
- Natural language instruction processing
- API key management in user-specific secure storage

### 3. Calendar Management (Output)
- Google Calendar and O365 integration via `CalendarProvider` interface
- OAuth-based authentication with token refresh
- 30-minute block allocation for scheduling
- Fixed appointment handling

## Web Framework Implementation

The application uses Flask with these key architectural elements:
- Application factory pattern (`create_app()`)
- Blueprint organization for route modularization
- Jinja2 templating with custom template directory
- Session and cookie-based authentication persistence

## Provider Pattern Implementation

Each service type follows a shared implementation pattern:

### Provider Interfaces
Each service type has an abstract base class with common methods:
- `_get_provider_name()`: Returns provider identifier
- `authenticate(email)`: Checks/refreshes credentials
- `get_credentials(email)`: Retrieves stored credentials
- `store_credentials(email, credentials)`: Securely stores credentials

### Manager Classes
Manager classes (`AIManager`, `TaskManager`) coordinate providers:
```python
def generate_text(self, email, prompt, provider_name=None):
    """Generate text using specified or default provider with fallback."""
    providers_to_try = (
        [self.providers[provider_name]] if provider_name
        else self.providers.values()
    )
    
    for provider in providers_to_try:
        try:
            return provider.generate_text(email, prompt)
        except Exception as e:
            logger.error(f"Error with {provider._get_provider_name()}: {e}")
            continue
```

## Task and Credential Management

### Todoist Provider Example
The TodoistProvider implements specific Todoist API interactions:
```python
def get_ai_instructions(self, email):
    """Get the AI instruction task content."""
    self._initialize_api(email)
    # Search for instruction task with specific title
    tasks = self.api.get_tasks(filter=f"search:{self.INSTRUCTION_TASK_TITLE}")
    instruction_task = next((t for t in tasks
                             if t.content == self.INSTRUCTION_TASK_TITLE), None)
    if instruction_task:
        return instruction_task.description
    return None
```

## Authentication Implementation

### Google Identity Services
- Client-side authentication using Google Identity Services API
- JWT token verification and email extraction
- Session and cookie-based persistence
- Backend credential verification:
```javascript
function handleCredentialResponse(response) {
    const responsePayload = jwt_decode(response.credential);
    const email = responsePayload.email;
    
    fetch('/login', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ email: email })
    })
}
```

## Calendar Integration

### OAuth Implementation
The application implements complete OAuth flows for calendar providers:

```python
def authenticate(self, email):
    """Authenticate with Google Calendar."""
    credentials = self.get_credentials(email)
    
    # Refresh expired tokens automatically
    if credentials and credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())
        self.store_credentials(email, credentials)
        return credentials
    
    # Start new OAuth flow when needed
    if not credentials or not credentials.valid:
        flow = Flow.from_client_config(
            client_config, scopes=self.scopes, redirect_uri=self.redirect_uri
        )
        authorization_url, state = flow.authorization_url(prompt="consent")
        session["oauth_state"] = state  # CSRF protection
        return None, authorization_url
        
    return credentials, None
```

## Data Models and Database

### Task Model
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

### Database Singleton Pattern
The system uses a Database singleton to manage the SQLAlchemy instance:

```python
class Database:
    """Database singleton class that wraps SQLAlchemy functionality."""
    _instance = None
    Model = db.Model
    session = db.session
    
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    @staticmethod
    def init_app(app):
        """Initialize the database with the Flask app"""
        db.init_app(app)
        # Get the singleton instance
        database = Database.get_instance()
```

## Database Architecture

The application uses a consolidated database approach:

### Central Database
- Single SQLAlchemy instance used throughout the application
- Shared database connection for all models
- User data is separated by user_id fields
- Models use consistent relationship patterns

### Database Models
- User model: Stores user authentication information
- CalendarAccount: Stores user's calendar provider credentials
- Additional models for tasks and other data as needed

### Implementation Strategy
- Database singleton class exposes shared SQLAlchemy components
- All models consistently use the same database connection
- Queries filter by user_id to maintain data isolation
- SQLAlchemy relationships maintain data integrity

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
- User data isolation through user_id filtering
- Secure JWT-based authentication
- Comprehensive logging with custom logger
- Exception handling with fallback mechanisms
- Session-based user state management

## UI Architecture

The application maintains a minimalist UI approach with only three primary user-facing pages:

### 1. Login Page
- Google Identity Services authentication
- JWT token verification
- Automatic user account creation
- Session/cookie management

### 2. Main Dashboard
- Central view displaying the AI-scheduled task blocks
- Calendar integration showing fixed appointments
- Navigation to configuration

### 3. Configuration Hub
- Task provider selection and authentication
- AI provider selection and API key management
- Calendar account management (connecting Google/O365)
- All configuration consolidated in a single flow

The UI design deliberately avoids page sprawl, with API provider setup, authentication flows, and management functions integrated into these three core pages rather than creating separate pages for each function.

The architecture emphasizes:
- Clean separation of concerns with Flask blueprints
- Consistent patterns across services
- Factory pattern for app and provider instantiation
- JWT-based Google authentication
- Blueprint organization for route modularization
- Dependency injection for flexible configuration
