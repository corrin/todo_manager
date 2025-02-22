# Todo Manager Architectural Overview

## Core Architecture

The system follows a provider-based architecture with three main components:

### 1. Task Management (Source)
- Todoist as the source system for tasks
- Tasks represent work items
- Single AI instruction task defines scheduling behavior
- Provider pattern for potential future task sources

### 2. AI Processing (Rules Engine)
- Multiple AI provider support (OpenAI, Grok, etc.)
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

## Data Flow

1. **Task Input**
   - Read tasks from Todoist
   - Read AI instructions
   - Track task status

2. **AI Processing**
   - AI provider reads tasks and instructions
   - Interprets scheduling requirements
   - Makes scheduling decisions
   - Uses user's provider credentials

3. **Calendar Output**
   - Calendar provider creates blocks
   - 30-minute allocations
   - Respects fixed appointments
   - Updates task status

## Authentication Flow

1. **User Setup**
   - User authenticates to system
   - User folder created
   - Provider setup initiated

2. **Provider Authentication**
   - Each provider checks credentials
   - Missing credentials trigger setup
   - Credentials stored per user
   - Regular validation checks

3. **Credential Management**
   - Secure credential storage
   - Provider-specific formats
   - Automatic refresh where supported
   - Clear error handling

## Implementation Structure

### AI Layer
- AIProvider interface
- Provider implementations (OpenAI, Grok)
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

## Next Steps

1. **Task Provider Implementation**
   - Create TaskProvider interface
   - Implement Todoist provider
   - Add instruction management
   - Integrate with AI system

2. **AI Provider Completion**
   - Complete Grok implementation
   - Add provider selection
   - Implement fallback logic
   - Add provider settings

3. **Integration Enhancement**
   - Unified credential management
   - Cross-provider operations
   - Error handling improvements
   - Monitoring and logging

The architecture emphasizes:
- Clean separation of concerns
- Consistent patterns across services
- User-specific credential management
- Extensibility for new providers
- Simple, natural language configuration