from datetime import datetime, timezone
from uuid import UUID, uuid4
from app.database import Base
from pydantic import BaseModel
from sqlalchemy import JSON, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column



def datetime_utcnow():
    return datetime.now(timezone.utc)

# The JSON body the browser sends to POST /chat.
class ChatRequest(BaseModel):
    conversation_id: str | None = None
    message: str


class Conversation(Base):
    __tablename__ = "conversations"
    id: Mapped[UUID] = mapped_column(default=uuid4, primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(default=datetime_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime_utcnow, onupdate=datetime_utcnow
    )

    def __repr__(self):
        return f'Conversation({self.id}, "{self.timestamp}", "{self.updated_at}")'

class Message(Base):
    __tablename__ = "messages"

    id: Mapped[UUID] = mapped_column(default=uuid4, primary_key=True)
    conversation_id: Mapped[UUID] = mapped_column(
        ForeignKey("conversations.id"), index=True
    )
    role: Mapped[str] = mapped_column(String(10))
    message: Mapped[list | str] = mapped_column(JSON)
    timestamp: Mapped[datetime] = mapped_column(default=datetime_utcnow)

    def __repr__(self):
        return f'Message({self.id}, "{self.conversation_id}", "{self.role}", "{self.message}, "{self.timestamp}"")'

