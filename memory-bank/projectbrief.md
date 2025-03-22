# Task Master Project Brief

## Project Purpose
Task Master is an intelligent task and meeting management assistant designed to help users organize work and schedule more effectively. The application takes a user's todo list and converts it into calendar appointments focused on tasks, following user-defined rules for time allocation.

## Core Requirements
1. **Task Management** - Integration with task providers (Todoist, SQLite) to collect and manage user tasks
2. **AI Processing** - Rules engine that processes natural language instructions to schedule tasks
3. **Calendar Management** - Integration with calendar providers (Google Calendar, O365) to create and manage scheduled events
4. **User Authentication** - Secure login and provider authentication flows
5. **Provider-based Architecture** - Modular design with provider interfaces for each component

## Project Goals
- Create a flexible system that converts tasks to optimized calendar appointments
- Support multiple task sources and calendar destinations
- Implement natural language rule processing (e.g., "work on maintaining friendships every week")
- Maintain a clean provider-based architecture for extensibility
- Build a minimal yet effective UI focused on core functionality
- Ensure secure handling of user credentials and data

## Key Constraints
- Strict provider pattern implementation
- User-specific credential storage
- Clean separation of concerns between components
- Minimal UI with focused functionality
- Security-first approach to credential handling

## Success Criteria
- Users can connect task providers and calendar accounts
- AI effectively schedules tasks based on natural language instructions
- System respects fixed appointments when scheduling
- Provider pattern allows for easy addition of new integrations
- User data is properly isolated and secured 