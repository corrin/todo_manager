# Technical Context

## Technologies Used

### Backend Framework
- **Flask**: Web framework for the application
- **Flask-Blueprints**: For route organization
- **Jinja2**: Templating engine

### Database
- **SQLAlchemy**: ORM for database operations
- **SQLite**: Database engine
- **Alembic**: Database migrations (implied)

### Authentication
- **Google Identity Services**: User authentication
- **OAuth2**: Provider authentication
- **PyJWT**: JWT token handling

### Task Management
- **Todoist API**: Primary task source
- **SQLite**: Alternative task storage

### AI Integration
- **OpenAI API**: Primary AI provider
- **Grok API**: Alternative AI provider (placeholder)

### Calendar Integration
- **Google Calendar API**: Primary calendar provider
- **Microsoft Graph API**: For Office 365 calendar integration

### DevOps/Development
- **Flask Debug**: Development server
- **ngrok**: Local tunneling for OAuth callbacks
- **pylint/flake8**: Code quality tools
- **pre-commit**: Git hooks
- **poetry/pip**: Dependency management

## Development Setup

### Local Development Requirements
- Python environment (3.x)
- ngrok for OAuth callbacks
- Google Cloud OAuth credentials
- Todoist API access
- OpenAI API key

### Environment Configuration
- `.env` file for environment variables
- `.flaskenv` for Flask configuration
- Local ngrok setup for OAuth callbacks

### Key Environment Variables
- `OPENAI_API_KEY`: For AI provider
- `GOOGLE_CLIENT_ID`: For authentication
- `GOOGLE_CLIENT_SECRET`: For OAuth
- `SECRET_KEY`: For Flask sessions
- `DATABASE_URI`: For database connection
- Additional provider-specific variables

## Technical Constraints

### Authentication Requirements
- User authentication through Google Identity
- Provider authentication through OAuth or API keys
- Secure credential storage with user isolation

### Provider Implementation
- All providers must implement their respective interfaces
- Manager classes must coordinate provider selection
- Error handling must follow established patterns

### Database Requirements
- Central database singleton for all operations
- User data isolation in all queries
- Consistent relationship patterns across models

### Dependency Constraints
- Minimize external dependencies
- Pin dependency versions
- Document all required environment variables

## Deployment Considerations

### Deployment Options
- Standalone Flask application
- Container-based deployment
- Requires secure environment for credential storage

### Infrastructure Requirements
- Persistent storage for database
- Secure credential storage
- HTTPS for all connections
- OAuth callback URLs configuration 