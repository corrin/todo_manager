# Task Master

An intelligent task and calendar management assistant that helps organize your work and schedule more effectively.

## Overview

Task Master integrates with your existing task management and calendar systems to provide intelligent scheduling based on your preferences. It takes your todo list and converts it into calendar appointments, following rules you define in natural language.

**Example rules you can specify:**
- "I want to work on maintaining my friendships every week"
- "Schedule my hobby project at least twice a week"
- "Reserve mornings for focused work"
- "Handle urgent tasks within 24 hours"

## Key Features

- **Multiple Provider Integration**
  - Task providers: Todoist, SQLite (local storage)
  - Calendar providers: Google Calendar, Microsoft 365
  - AI providers: OpenAI (GPT)

- **Intelligent Scheduling**
  - Natural language rule processing
  - Task prioritization and organization
  - Time block allocation based on your preferences

- **Seamless Authentication**
  - Google Identity Services for app authentication
  - OAuth integration with calendar services
  - Secure credential management

- **Clean User Interface**
  - Single-page configuration hub
  - Comprehensive settings management
  - Calendar and task synchronization

## Architecture

Task Master follows a provider-based architecture with clean separation of concerns:

1. **Task Management** - Retrieves and organizes tasks from various sources
2. **AI Processing** - Processes natural language rules and generates schedules
3. **Calendar Management** - Syncs and manages events across calendar providers
4. **Authentication** - Handles user authentication and service credentials
5. **Database** - Manages persistent data with SQLAlchemy ORM

See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed architectural information.

## Implementation Status

- ✅ Core application structure and provider architecture
- ✅ Google and Microsoft 365 calendar integration
- ✅ OpenAI provider integration
- ✅ Authentication flows with Google Identity Services
- ✅ Calendar synchronization and management
- ✅ Database models and ORM integration
- ⏳ Todoist and SQLite provider implementation (needs testing)
- ⏳ Task UI components
- 🔲 Outlook and Google Tasks providers (planned)

See [IMPLEMENTATION.md](IMPLEMENTATION.md) for details on implementation status.

## Getting Started

For local development setup instructions, see [local_setup.md](local_setup.md).

## License

This project is licensed under the GPL License - see the LICENSE file for details.


