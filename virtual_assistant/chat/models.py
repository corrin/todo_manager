import uuid
from datetime import datetime, timezone
from virtual_assistant.database.database import db
from virtual_assistant.database.user import MySQLUUID


class Conversation(db.Model):
    __tablename__ = "conversation"

    id = db.Column(MySQLUUID(), primary_key=True, default=uuid.uuid4)
    user_id = db.Column(MySQLUUID(), db.ForeignKey("user.id"), nullable=False)
    title = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    messages = db.relationship(
        "ChatMessage",
        backref="conversation",
        lazy=True,
        order_by="ChatMessage.sequence",
        cascade="all, delete-orphan",
    )

    def next_sequence(self):
        last = ChatMessage.query.filter_by(
            conversation_id=self.id
        ).order_by(ChatMessage.sequence.desc()).first()
        return (last.sequence + 1) if last else 0

    @staticmethod
    def get_history(conversation_id):
        messages = ChatMessage.query.filter_by(
            conversation_id=conversation_id
        ).order_by(ChatMessage.sequence).all()
        return [msg.to_dict() for msg in messages]

    def __repr__(self):
        return f"<Conversation {self.id} user={self.user_id}>"


class ChatMessage(db.Model):
    __tablename__ = "chat_message"

    id = db.Column(MySQLUUID(), primary_key=True, default=uuid.uuid4)
    conversation_id = db.Column(
        MySQLUUID(), db.ForeignKey("conversation.id"), nullable=False
    )
    role = db.Column(db.String(20), nullable=False)
    content = db.Column(db.Text, nullable=True)
    tool_calls = db.Column(db.JSON, nullable=True)
    tool_call_id = db.Column(db.String(255), nullable=True)
    sequence = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        d = {"role": self.role, "content": self.content or ""}
        if self.tool_calls:
            d["tool_calls"] = self.tool_calls
        if self.tool_call_id:
            d["tool_call_id"] = self.tool_call_id
        return d

    def __repr__(self):
        return f"<ChatMessage {self.id} role={self.role}>"
