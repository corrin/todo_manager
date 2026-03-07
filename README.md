# Task Master

An intelligent task and calendar management assistant that helps organize your work and schedule more effectively.

## Overview

Task Master is an AI-based scrum master that helps you manage your time and tasks effectively. It functions by:
a) Receiving feedback from you on what you've been doing and what you've accomplished (daily or multiple times a day).
b) Reviewing your goals, including how you want to spend your time and what you want to accomplish.
c) Refining and rewriting your plan to align with the new information and your progress.
d) Breaking down large goals into smaller, manageable tasks as they become more imminent.
e) Minimizing context switching, for example, by organizing your week into larger blocks of time rather than frequent, small task changes.

**Example User Goals:**
- "I want to do something social every week."
- "I want to spend 30% of my time on F&P."
- "I want to achieve something on MSM every week."
- "I want to achieve something on a personal project every week."
- "I want to achieve something on Massey smiles at least once a month."
- "Reserve mornings for focused work."
- "Handle urgent tasks within 24 hours."

## Key Features

- **Multiple Provider Integration:** Connects with various task management and calendar systems to gather your data and update your schedule.

- **AI-Powered Planning & Adaptation:** 
  - Aligns your schedule with your stated goals and priorities.
  - Dynamically refines your plan based on your progress and feedback.
  - Breaks down large objectives into actionable tasks.
  - Optimizes your schedule to minimize context switching and enhance focus.

## Architecture

Task Master follows a provider-based architecture with clean separation of concerns:

1. **Task Management** - Retrieves and organizes tasks and goals from external providers (like Todoist, with Google/Outlook Tasks in development) and caches them in a local database.
2. **AI Processing** - Analyzes goals and feedback, adapts plans, breaks down objectives, and generates schedules.
3. **Calendar Management** - Outputs the generated plan and tasks to the user's calendar.
4. **Authentication** - Handles user authentication (primarily database-centric with Google Sign-In) and service credentials.
5. **Database** - Manages persistent data including user accounts, credentials, and a central task cache with SQLAlchemy ORM.

See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed architectural information.

## Implementation Status

- ⏳ Todoist provider integration (needs comprehensive testing).
- ⏳ Core features for Google Tasks and Outlook Tasks integration (task fetching) are in development; full task modification capabilities are planned.
- ⏳ Ongoing UI development for task and plan management.

See [IMPLEMENTATION.md](IMPLEMENTATION.md) for details on implementation status.

## Getting Started

For local development setup instructions, see [local_setup.md](local_setup.md).

## License

This project is licensed under the GPL License - see the LICENSE file for details.


