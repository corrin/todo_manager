import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import JSON, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from virtual_assistant.database.database import Base
from virtual_assistant.database.user import MySQLUUID


class Conversation(Base):
    __tablename__ = "conversation"

    id: Mapped[uuid.UUID] = mapped_column(MySQLUUID(), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(MySQLUUID(), ForeignKey("app_user.id"))
    title: Mapped[Optional[str]] = mapped_column(String(255), default=None)
    created_at: Mapped[Optional[datetime]] = mapped_column(default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    messages = relationship(
        "ChatMessage",
        backref="conversation",
        lazy=True,
        order_by="ChatMessage.sequence",
        cascade="all, delete-orphan",
    )

    def next_sequence(self):
        last = ChatMessage.query.filter_by(conversation_id=self.id).order_by(ChatMessage.sequence.desc()).first()
        return (last.sequence + 1) if last else 0

    @staticmethod
    def get_history(conversation_id):
        messages = ChatMessage.query.filter_by(conversation_id=conversation_id).order_by(ChatMessage.sequence).all()
        return [msg.to_dict() for msg in messages]

    def __repr__(self):
        return f"<Conversation {self.id} user={self.user_id}>"


class ChatMessage(Base):
    __tablename__ = "chat_message"

    id: Mapped[uuid.UUID] = mapped_column(MySQLUUID(), primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(MySQLUUID(), ForeignKey("conversation.id"))
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[Optional[str]] = mapped_column(default=None)
    tool_calls: Mapped[Optional[Any]] = mapped_column(type_=JSON, default=None)
    tool_call_id: Mapped[Optional[str]] = mapped_column(String(255), default=None)
    sequence: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[Optional[datetime]] = mapped_column(default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        d = {"role": self.role, "content": self.content or ""}
        if self.tool_calls:
            d["tool_calls"] = self.tool_calls
        if self.tool_call_id:
            d["tool_call_id"] = self.tool_call_id
        return d

    def __repr__(self):
        return f"<ChatMessage {self.id} role={self.role}>"
