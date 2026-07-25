from uuid import UUID
from sqlalchemy import select
from sqlalchemy.orm import Session
from datetime import date 
from app.database import PgSession, MySQLSession
from app.models import Conversation, Message, Combination, Detail, Unit, Allotment, Destination, SeasonCalendar, ExchangeRate 
HOTEL_NAME_TO_ID = {
    "antigua": 1,
    "pacifico": 2,
}

def conversation_exists(conversation_id):
    with PgSession() as session:
       
        conversation = session.get(Conversation, UUID(conversation_id))
        if conversation is None:
            return False
        else:
            return True


def create_conversation(conversation_id):
    with PgSession() as session:
        conversation = Conversation(id=UUID(conversation_id))
        session.add(conversation)
        session.commit()


def save_message(conversation_id, role, message):
    with PgSession() as session:
        new_message = Message(
            conversation_id=UUID(conversation_id),
            role=role,
            message=message,
        )
        session.add(new_message)
        session.commit()


def load_history(conversation_id):
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



def get_room_combinations(hotel, adults,children):
    hotel = HOTEL_NAME_TO_ID[hotel]
    with MySQLSession() as session:
        query = (
            select(
                Combination,
                Detail,
                Unit)
            .join(Combination.details)
            .join(Detail.unit)
            .where(
                Combination.hotel == hotel,
                Combination.adults == adults,
                Combination.children == children,
                Combination.active == 1,   
            )
            .order_by(Combination.priority, Combination.id)
        )
        rows = session.execute(query).all()
        return rows


def check_availability(hotel, room, check_in, check_out):
    hotel = HOTEL_NAME_TO_ID[hotel]
    with MySQLSession() as session:
        query = (
            select(Allotment, Unit)
            .join(Unit, Allotment.code == Unit.code)
            .where(
                Allotment.hotel == hotel,
                Unit.room == room,
                Allotment.estado == "DISPONIBLE",
                Allotment.check_in == check_in,
                Allotment.check_out == check_out,
            )
        )
        rows = session.execute(query).all()

        available_rooms = []
        for allotment, unit in rows:
            available_rooms.append({
                "hotel": allotment.hotel,
                "code": allotment.code,
                "room": unit.room,
                "check_in": allotment.check_in,
                "check_out": allotment.check_out,
            })
        return available_rooms

def nights_query(check_in, check_out):
    with MySQLSession() as session:
        query = (
            select(SeasonCalendar)
            .where(
                SeasonCalendar.calendar >= check_in,
                SeasonCalendar.calendar < check_out,
            )
            .order_by(SeasonCalendar.calendar)
        )
        nights = session.scalars(query).all()
        return nights 
def get_exchange_rate(session):
    query = (
        select(ExchangeRate)
        .where(ExchangeRate.today <= date.today())
        .order_by(ExchangeRate.today.desc())
    )
    return session.scalars(query).first()

def get_quote(hotel, code, check_in, check_out):
    SEASON_NAME_TO_CODE = {
    "ENTRE SEMANA": "ENTRE",
    "FIN DE SEMANA": "FIN",
    "SUPER ALTA": "SUP_AL",
    }
    nights = nights_query(check_in, check_out)
    hotel = HOTEL_NAME_TO_ID[hotel]
    
    with MySQLSession() as session:
        exchange_rate = get_exchange_rate(session)
        query = (
            select(Destination, Unit)
            .join(Unit, Unit.code == Destination.code)
            .where(
                tipo_unid.hotel == hotel,
                Destination.points > 0,
                Destination.code == code,
                Destination.year.like("2026%"),
                Destination.hotel == hotel,
            )
        )
        rows = session.execute(query).all()

        room_name = None
        points_by_season = {}
        for destination, unit in rows:
            room_name = unit.room
            points_by_season[destination.season] = destination.points

    total_points = 0
    for night in nights:
        total_points = total_points + points_by_season[SEASON_NAME_TO_CODE[night.season]]
    price = total_points * 4.5 * exchange_rate.rate
    
    return {
        "room": room_name,
        "nights": len(nights),
        "total_points": total_points,
        "rate": exchange_rate.rate,
        "price": round(price, 2),
    }
