from app.database import PgSession
from sqlalchemy import select, text, func, update
from sqlalchemy.orm import Session
from app.models import Conversation, Message, RoomCombinations, RoomTypes, RoomRates, Allotments, Calendar, Contracts

def get_exchange_rate():
    with PgSession() as session:
        query = (select(Calendar.exchange_rate)
        .where(Calendar.calendar_date == func.current_date())
        )
        rate = session.scalar(query)
        return rate

def update_quetzales():
    rate = get_exchange_rate()
    with PgSession() as session:
        result = session.execute(
            update(RoomRates).values(quetzales=RoomRates.dollars * rate)
        )
        session.commit()
        return {"rate": rate, "updated": result.rowcount}
