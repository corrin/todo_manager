# Task Master Architecture

## System Overview

Task Master is built on Flask and follows a provider-based architecture with five main components:

### 1. Task Management
- **Task Providers**: Integrations with task sources
  - **Todoist**: API-based integration using Todoist Python SDK
  - **SQLite**: Local storage implementation
  - **Outlook Tasks**: Microsoft Graph API integration (placeholder)
  - **Google Tasks**: Google Tasks API integration (placeholder)
- **Task Representation**: Standardized `Task` dataclass across providers
- **Task Hierarchy**: Support for projects, sections, and parent-child relationships

### 2. AI Processing
- **AI Providers**: Integrations with AI services
  - **OpenAI**: Complete implementation with API key management
  - **Grok**: Placeholder implementation
- **Instruction Processing**: Natural language rule interpretation
- **Credential Management**: User-specific API key storage

### 3. Calendar Management
- **Calendar Providers**: Calendar service integrations
  - **Google Calendar**: Complete implementation with OAuth
  - **Office 365**: Complete implementation with OAuth via Microsoft Graph API
- **Event Handling**: Creation, retrieval, updating, and deletion
- **Synchronization**: Calendar account synchronization with error handling
- **Token Management**: Automatic token refresh with reauthorization flows

### 4. Authentication
- **User Authentication**: Google Identity Services integration
- **Provider Authentication**: OAuth for calendar providers, API keys for others
- **Session Management**: Flask-Login and session-based user state
- **Credential Storage**: Mix of database and file-based credential storage

### 5. Database
- **ORM Integration**: SQLAlchemy with Flask-SQLAlchemy
- **Core Models**: User, CalendarAccount, Task with relationships
- **Migration Support**: Alembic/Flask-Migrate for schema evolution
- **Data Isolation**: User-specific data filtering in all queries

## Web Framework Implementation

The application uses Flask with these key architectural elements:
- **Application Factory**: `create_app()` pattern for Flask initialization
- **Blueprint Organization**: Modular route design by feature area
- **Dependency Injection**: Factory functions for service instantiation
- **Background Processing**: Threading for token refresh operations
- **Error Handling**: Centralized exception management

## Provider Pattern Implementation

All service integrations follow the provider pattern:

### Provider Interfaces

Each service type implements an abstract base class defining its contract:

#### AIProvider Interface
- Abstract methods for authentication, credentials management, and text generation
- Consistent error handling across implementations
- Support for fallback between providers

#### TaskProvider Interface
- Methods for task retrieval, creation, and status updates
- Special handling for instruction tasks
- Authentication and credential management

#### CalendarProvider Interface
- OAuth authentication and token management
- Event CRUD operations
- Synchronization capabilities
- Token refresh and reauthorization

### Factory Pattern

Provider factories handle the creation of specific provider instances:

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

Manager classes coordinate between multiple providers:

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
        # ... additional methods
```

## Database Architecture

### Database Singleton
- Centralized SQLAlchemy instance managed through `Database` class
- Application context-aware connection management
- Blueprint for database routes with API endpoints

### Data Models
- **User**: Authentication information with relationships to accounts
- **CalendarAccount**: Provider-specific calendar accounts with credentials
- **Task**: Task details with comprehensive fields and relationships

### Migration System
- Version-controlled schema evolution
- Clean upgrade/downgrade paths
- Integration with application startup

## Authentication Implementation

### User Authentication
- Google Identity Services for JWT-based authentication
- User creation and session establishment
- Cookie-based persistence for sessions

### Provider Authentication
- **OAuth Flow**:
  1. Redirect to provider's consent screen
  2. Authorization code handling
  3. Token exchange
  4. Credential storage
  5. Automatic token refresh
- **API Key Management**:
  - Secure storage of provider API keys
  - User-specific credential files
  - Settings page for credential management

## Task System Implementation

### Task Data Model
```python
@dataclass
class Task:
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

### Task Hierarchy
- Projects and sections organization
- Parent-child task relationships
- Priority-based ordering
- Special handling for instruction tasks

## Calendar Integration

### OAuth Implementation
- Complete flow with authorization, token exchange, and refresh
- Provider-specific permission scopes
- Error handling for expired or invalid tokens
- Reauthorization for permanently invalid credentials

### Calendar Synchronization
- Periodic background synchronization
- On-demand synchronization endpoints
- Error isolation between accounts
- User feedback for synchronization status

### Calendar Event Handling
- Consistent event representation across providers
- CRUD operations for calendar events
- Time zone handling (with some known challenges)
- Conflict detection for overlapping events

## Flask Application Structure

### Core Components
- `flask_app.py`: Main application factory and routes
- `settings.py`: Environment-based configuration
- `logger.py`: Custom logging implementation

### Blueprint Organization
- `/ai`: AI provider routes and authentication
- `/tasks`: Task provider routes and management
- `/meetings`: Calendar integration and synchronization
- `/database`: Database API endpoints and operations

### Template Structure
- Login page with Google authentication
- Settings page for provider configuration
- Task management interface
- Error templates for feedback

## Background Processing

### Token Refresh Scheduler
- Background thread for periodic token verification
- Asynchronous processing for O365 operations
- Error handling with retries and logging

### Batch Operations
- Account-by-account calendar synchronization
- Error isolation between operations
- Result aggregation for user feedback

## Security Considerations

### Credential Management
- Database storage for OAuth tokens
- File-based storage for API keys
- Session-based user state
- Access control for all operations

### Data Isolation
- User-specific filtering in all database queries
- Clear ownership boundaries for all data
- No cross-user data access in standard operations

## Known Architecture Issues

### User Management Inconsistency
- Two competing approaches:
  - File-based user management in `auth/user_manager.py`
  - Database-based user management in `database/user_manager.py`
- Need for consolidation to database-only approach

### Calendar Integration Challenges
- Time zone handling issues
- Token refresh reliability
- OAuth error handling improvements needed

### Task Provider Completeness
- Todoist and SQLite providers need testing
- Outlook and Google Tasks providers are placeholders

## UI Architecture

The application maintains a minimalist approach with three primary pages:

### Login Page
- Google Identity Services authentication
- Session establishment
- Redirect to main dashboard

### Main Dashboard
- Task display and management
- Calendar integration
- Navigation to settings

### Settings Page
- Provider configuration
- API key management
- Calendar account management
- Synchronization controls

## Future Architectural Considerations

- Complete migration to database-only user management
- Development of API endpoints to support user-centric tools (e.g., browser extensions or mobile clients for data input and plan review).
- Enhanced error handling and user feedback
- UI component implementation for task management
