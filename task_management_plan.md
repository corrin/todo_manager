# Task Management System Plan

## Authentication Flow

1. **System Authentication**
   - User authenticates via Google (existing)
   - Creates user-specific secure storage

2. **Service Credentials**
   - Store Todoist API key per user
   - Store calendar credentials per user (existing)
   - All secured behind Google authentication

## Components

### 1. Credential Management
- Extend UserManager to handle Todoist credentials
- Store API keys in user-specific folders
- Access controlled via Google authentication

### 2. Chat Interface
- Requires Google authentication
- Natural language interaction
- Commands for:
  - Task management
  - Schedule queries
  - Status updates

### 3. Todoist Integration
- Read/write access via stored API key
- Operations:
  - Task management
  - Project access
  - Rules reading (from Rules project)

### 4. Calendar Integration
- Existing Google/O365 support
- 30-minute block management
- Schedule creation

### 5. LLM Processing
- Command interpretation
- Rule application
- Schedule generation
- Natural responses

## Implementation Steps

1. **Credential Management**
   - Add Todoist credential methods to UserManager
   - Implement secure storage
   - Add credential validation

2. **Basic Integration**
   - Implement Todoist API connection
   - Test basic task reading
   - Verify project access

3. **Chat Interface**
   - Create basic command processing
   - Add task display functionality
   - Implement status updates

4. **Scheduling Logic**
   - Implement rule reading
   - Add schedule generation
   - Connect to calendar

## Next Steps

1. Extend UserManager for Todoist credentials
2. Implement basic Todoist API connection
3. Create simple chat interface
4. Add task display functionality

This approach:
- Leverages existing authentication
- Maintains security
- Follows established patterns
- Allows for multi-user expansion