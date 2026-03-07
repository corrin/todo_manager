# Virtual Assistant (Task Master)

## Project Overview
A Flask-based virtual assistant that integrates task management, calendar, and AI services. Uses a provider-based architecture with support for multiple backends (Google, O365, Todoist, OpenAI).

## Project Structure
- `virtual_assistant/` - Main Python package
  - `flask_app.py` - Application factory and core routes (the real entry point)
  - `__init__.py` - Secondary app factory (simpler, used by migrations)
  - `ai/` - AI provider integrations (OpenAI, Grok placeholder)
  - `auth/` - Authentication (Google Identity Services, Flask-Login)
  - `database/` - SQLAlchemy models (User, ExternalAccount, Task/TaskAccount)
  - `meetings/` - Calendar providers (Google Calendar, O365)
  - `tasks/` - Task providers (Todoist, SQLite, Outlook, Google Tasks)
  - `schedule/` - Schedule generation routes
  - `templates/` - Jinja2 HTML templates
  - `static/` - CSS, JS, favicon
  - `utils/` - Settings, logger
- `migrations/` - Alembic/Flask-Migrate schema migrations
- `memory-bank/` - Legacy context files (from Cursor)
- `oneoff/` - One-off scripts

## Tech Stack
- Python 3.12, Flask, SQLAlchemy, Flask-Migrate (Alembic)
- Poetry for dependency management
- Flask-Login for session management
- Google Identity Services for user auth
- OAuth for calendar/task provider auth

## Key Patterns
- Provider pattern: abstract base classes with concrete implementations
- Factory pattern for provider instantiation
- Application factory (`create_app()`) in `flask_app.py`
- Manager classes coordinate multiple providers

## Running
- `.flaskenv` sets `FLASK_APP=virtual_assistant.flask_app`
- `poetry run flask run` to start the dev server

## Database
- SQLAlchemy ORM with Flask-SQLAlchemy
- Models: User, ExternalAccount, TaskAccount, Task
- Alembic migrations in `migrations/`
- ExternalAccount unifies calendar account management (was CalendarAccount)

## Current State (as of last work)
- Core architecture complete
- Calendar providers (Google, O365) working
- OpenAI provider working
- Grok provider is a placeholder (remove or implement)
- Task providers need testing (Todoist, SQLite)
- Outlook/Google Tasks providers are stubs
- ExternalAccount refactor partially complete (see memory-bank/external_account_refactor.md)
- Dual user management systems need consolidation (prefer DB approach)

## Package Name
The package is `virtual_assistant`. All internal imports use `virtual_assistant.*`.
