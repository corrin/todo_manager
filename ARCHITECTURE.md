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
Each service type has an abstract base class, but with different methods depending on the provider type:

**AIProvider Interface:**
- `_get_provider_name()`: Returns provider identifier
- `authenticate(email)`: Checks/refreshes credentials
- `get_credentials(email)`: Retrieves stored credentials
- `store_credentials(email, credentials)`: Securely stores credentials
- `generate_text(email, prompt)`: Generates text using the AI provider

**CalendarProvider Interface:**
- `authenticate(email)`: Checks/refreshes credentials
- `retrieve_tokens(callback_url)`: Processes OAuth callback
- `get_meetings(email)`: Retrieves calendar meetings
- `create_meeting(email, event_data)`: Creates a new calendar event
- `get_credentials(email)`: Retrieves stored credentials

### Manager Classes
Manager classes (`AIManager`, `TaskManager`) coordinate providers and implement fallback logic between different providers. See `ai_manager.py` for implementation details.

## Task and Credential Management

### Todoist Provider Example
The TodoistProvider implements specific Todoist API interactions to retrieve tasks and AI instructions. See `todoist_provider.py` for implementation details.

## Authentication Implementation

### Google Identity Services
- Client-side authentication using Google Identity Services API
- JWT token verification and email extraction
- Session and cookie-based persistence
- Backend credential verification through login endpoint

## Calendar Integration

### OAuth Implementation
The application implements complete OAuth flows for connecting to users' calendar accounts (Google Calendar, O365). This allows users to grant the application access to their calendar data without sharing their credentials. The implementation includes automatic token refresh and state management for the authorization flow. See `google_calendar_provider.py` and `o365_calendar_provider.py` for implementation details.

## Data Models and Database

### Task Model
The system uses a standardized Task model across providers with fields for ID, title, project, priority, due date, status, and instruction flag. See `task_module.py` for the complete implementation.

### Database Singleton Pattern
The system uses a Database singleton to manage the SQLAlchemy instance, providing centralized access to database models and sessions. See `database.py` for implementation details.

## Database Architecture

The application uses a consolidated database approach:

### Central Database
- Single SQLAlchemy instance used throughout the application
- Shared database connection for all models
- User data is separated by app_user_email fields
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

## Coding Standards

### 1. Import Organization
- All imports must be at the top of the file
- Standard library imports first, followed by third-party imports, then local imports
- No imports inside functions or methods
- Group imports logically (e.g., all Flask imports together)

### 2. Error Handling Principles
- Fail early: Detect and report errors as soon as possible
- Don't use if statements to hide errors - raise exceptions when appropriate
- Trust other functions to have done their job - avoid redundant checks
- TRUST THE DATA MODEL.  If a field is required, then you do not need to check it is present.  
- DO NOT USE FALLBACKS. If something is wrong then STOP.
- Use specific exception types rather than generic exceptions
- Log errors with appropriate context information

### 3. Function Design
- Functions should do one thing and do it well
- Keep functions small and focused
- Use descriptive function and variable names
- Document function parameters and return values
- Use type hints where appropriate

### 4. Code Organization
- Follow consistent patterns across similar components
- Use classes to encapsulate related functionality
- Maintain separation of concerns between modules
- Use dependency injection for flexible configuration
- Follow the provider pattern for service implementations

### 5. Database Operations
- Use SQLAlchemy models consistently
- Ensure proper transaction management
- Handle database errors appropriately
- Use migrations for schema changes
- Validate data before storing in the database

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
