# AI Chatbot Design

## Summary

Add a task-focused AI chatbot as the primary interface for the Aligned app. The chatbot helps users break down tasks, report progress, reorder priorities, and manage their schedule through natural conversation. The chat page includes a live dashboard showing calendar and task state.

## Architecture

### Page Layout

Two-panel layout on `/chat` (becomes the default landing page for logged-in users):

- **Left (~60%)**: Chat panel with message history and input
- **Right (~40%)**: Dashboard panel showing today's calendar and active tasks
- **Mobile**: Dashboard collapses below chat or into a toggle tab
- **Navigation simplifies to**: Chat, Settings, Logout

### Chat UI (Frontend)

- Vanilla JS chat component (~100-150 lines) in a Jinja2 template
- No build step -- script tags only, consistent with existing Flask templates
- SSE streaming via `fetch()` with readable stream
- Markdown rendering via `marked.js` (CDN)
- Dashboard panel refreshes when AI tool calls modify state

### Chat API (Backend)

**`POST /api/chat`** (SSE streaming endpoint)
- Input: `{ message, conversation_id? }`
- Output: Server-Sent Events stream of tokens
- Creates new conversation if `conversation_id` not provided

**Streaming flow:**
1. User sends message -> JS fetches `/api/chat`
2. Flask saves user message, calls `litellm.completion(stream=True, tools=...)`
3. Tokens streamed back as SSE
4. If AI requests tool call -> execute server-side, feed result back to LiteLLM, continue streaming
5. Save final assistant message + tool calls to DB
6. JS triggers dashboard refresh if tools modified state

**`GET /api/dashboard`**
- Returns today's calendar events + active tasks as JSON
- Called on page load and after tool-call mutations

### LiteLLM Integration

- Replaces current `OpenAIProvider.generate_text` single-shot approach
- `litellm.completion()` with `stream=True`
- Model configurable per user in settings (e.g., `gpt-4o`, `claude-sonnet-4-20250514`)
- User's API key passed through
- OpenAI-format function/tool definitions for task and calendar operations

### AI Tool Definitions

Initial set of tools the AI can call:

- `get_tasks(status?, priority?)` -- list tasks with optional filters
- `complete_task(task_id)` -- mark a task as done
- `create_task(title, description?, priority?)` -- create a new task
- `update_task(task_id, ...)` -- modify priority, description, etc.
- `break_down_task(task_id, subtasks)` -- split a task into subtasks
- `reorder_tasks(task_ids_in_order)` -- set task priority order
- `get_calendar(date?)` -- get calendar events for a day
- `get_schedule()` -- today's schedule overview

### Database Schema

Two new tables:

**`conversation`**
- `id` (UUID, PK)
- `user_id` (FK -> user.id)
- `title` (string, nullable -- auto-generated from first message)
- `created_at` (datetime)
- `updated_at` (datetime)

**`chat_message`**
- `id` (UUID, PK)
- `conversation_id` (FK -> conversation.id)
- `role` (enum: user, assistant, system, tool)
- `content` (text)
- `tool_calls` (JSON, nullable -- for assistant tool call requests)
- `tool_call_id` (string, nullable -- for tool response messages)
- `created_at` (datetime)

### Dependencies

- Add: `litellm` (Python, via Poetry)
- Add: `marked.js` (CDN, frontend markdown rendering)

## What Changes

- `/chat` becomes the new default landing page for logged-in users
- `index` route redirects to `/chat`
- Current index.html task/calendar buttons replaced by chat-driven interaction
- Navigation simplifies to: Chat, Settings, Logout
- `OpenAIProvider` usage migrates to LiteLLM (but existing provider code remains for now)

## Out of Scope (Future)

- Conversation search/history browser
- File/image attachments in chat
- Multiple simultaneous conversations
- Voice input
- Advanced calendar views (week/month) in dashboard
