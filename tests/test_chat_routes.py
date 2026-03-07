import uuid
from unittest.mock import MagicMock, patch

import pytest

from virtual_assistant.chat.models import ChatMessage, Conversation
from virtual_assistant.database.database import db
from virtual_assistant.database.user import User
from virtual_assistant.flask_app import create_app


@pytest.fixture()
def app():
    app = create_app()
    app.config.update(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SERVER_NAME": "localhost",
        }
    )
    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()


@pytest.fixture()
def user(app):
    with app.app_context():
        u = User(app_login="test@example.com")
        u.ai_api_key = "sk-test-key"
        db.session.add(u)
        db.session.commit()
        yield u


@pytest.fixture()
def client(app):
    return app.test_client()


def _login(client, user):
    """Simulate Flask-Login session."""
    with client.session_transaction() as sess:
        sess["_user_id"] = str(user.id)


def test_chat_endpoint_requires_message(app, client, user):
    """POST /api/chat with empty body returns 400."""
    _login(client, user)
    resp = client.post("/api/chat", json={})
    assert resp.status_code == 400
    data = resp.get_json()
    assert "error" in data or "message" in data


def test_chat_creates_conversation(app, client, user):
    """POST /api/chat creates a conversation and returns assistant response."""
    _login(client, user)

    with patch("virtual_assistant.chat.chat_routes.litellm") as mock_llm:
        mock_choice = MagicMock()
        mock_choice.message.content = "Hello!"
        mock_choice.message.tool_calls = None
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_llm.completion.return_value = mock_response

        resp = client.post("/api/chat", json={"message": "Hi there"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert "conversation_id" in data
        assert data["content"] == "Hello!"

    # Verify conversation exists in DB
    with app.app_context():
        convs = Conversation.query.filter_by(user_id=user.id).all()
        assert len(convs) == 1
        assert convs[0].title == "Hi there"[:100]


def test_dashboard_endpoint(app, client, user):
    """GET /api/dashboard returns tasks structure."""
    _login(client, user)
    resp = client.get("/api/dashboard")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "tasks" in data
    assert "prioritized" in data["tasks"]
    assert "unprioritized" in data["tasks"]
    assert "completed" in data["tasks"]
    assert "events" in data
