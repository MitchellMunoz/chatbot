from uuid import UUID
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import PgSession, MySQLSession
from app.models import Conversation, Message


def conversation_exists(conversation_id: str) -> bool:
    with PgSession() as session:
        #SELECT * FROM conversations WHERE conversations.id = :your_uuid
        #conversation = session.scalars(
        #select(Conversation).where(Conversation.id == UUID(conversation_id))
        #).first()
        conversation = session.get(Conversation, UUID(conversation_id))
        if conversation is None:
            return False
        else:
            return True


def create_conversation(conversation_id: str) -> None:
    with PgSession() as session:
        conversation = Conversation(id=UUID(conversation_id))
        session.add(conversation)
        session.commit()


def save_message(conversation_id: str, role: str, message: str) -> None:
    with PgSession() as session:
        new_message = Message(
            conversation_id=UUID(conversation_id),
            role=role,
            message=message,
        )
        session.add(new_message)
        session.commit()


def load_history(conversation_id: str) -> list:
    with PgSession() as session:
        query = (
            select(Message)
            .where(Message.conversation_id == UUID(conversation_id))
            .order_by(Message.timestamp)
        )
        rows = session.scalars(query).all()

        history = []
        for row in rows:
            history.append({"role": row.role, "content": row.message})
        return history