import uuid

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
        db.session.add(u)
        db.session.commit()
        yield u


def test_create_conversation(app, user):
    with app.app_context():
        conv = Conversation(user_id=user.id, title="Test chat")
        db.session.add(conv)
        db.session.commit()

        assert conv.id is not None
        assert conv.user_id == user.id
        assert conv.title == "Test chat"


def test_create_chat_message(app, user):
    with app.app_context():
        conv = Conversation(user_id=user.id)
        db.session.add(conv)
        db.session.commit()

        msg = ChatMessage(
            conversation_id=conv.id,
            role="user",
            content="Hello",
        )
        db.session.add(msg)
        db.session.commit()

        assert msg.id is not None
        assert msg.role == "user"
        assert msg.content == "Hello"


def test_conversation_messages_relationship(app, user):
    with app.app_context():
        conv = Conversation(user_id=user.id)
        db.session.add(conv)
        db.session.commit()

        msg1 = ChatMessage(conversation_id=conv.id, role="user", content="Hi", sequence=0)
        msg2 = ChatMessage(conversation_id=conv.id, role="assistant", content="Hello!", sequence=1)
        db.session.add_all([msg1, msg2])
        db.session.commit()

        assert len(conv.messages) == 2
        assert conv.messages[0].content == "Hi"
        assert conv.messages[1].content == "Hello!"


def test_tool_call_message(app, user):
    with app.app_context():
        conv = Conversation(user_id=user.id)
        db.session.add(conv)
        db.session.commit()

        msg = ChatMessage(
            conversation_id=conv.id,
            role="assistant",
            content="",
            tool_calls=[{"id": "call_1", "function": {"name": "get_tasks", "arguments": "{}"}}],
        )
        db.session.add(msg)
        db.session.commit()

        assert msg.tool_calls[0]["function"]["name"] == "get_tasks"


def test_get_conversation_history(app, user):
    with app.app_context():
        conv = Conversation(user_id=user.id)
        db.session.add(conv)
        db.session.commit()

        msgs = [
            ChatMessage(conversation_id=conv.id, role="user", content="Hi", sequence=0),
            ChatMessage(conversation_id=conv.id, role="assistant", content="Hello!", sequence=1),
        ]
        db.session.add_all(msgs)
        db.session.commit()

        history = Conversation.get_history(conv.id)
        assert len(history) == 2
        assert history[0]["role"] == "user"
        assert history[1]["role"] == "assistant"
