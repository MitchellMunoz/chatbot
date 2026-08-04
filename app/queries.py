from uuid import UUID
from decimal import Decimal
from sqlalchemy import select, text, update
from sqlalchemy.orm import Session
from datetime import date
from app.database import PgSession, MySQLSession
from app.models import Conversation, Message, RoomCombinations, RoomTypes, RoomRates, Allotments, Calendar, Members, Points
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

GT = ZoneInfo("America/Guatemala")
now = datetime.now(GT)


def get_room_points(room_code, check_in, check_out):

    with PgSession() as session:
        query = (
            select(
                Calendar.calendar_date,
                RoomRates.time_of_the_week,
                RoomRates.points,
                RoomRates.dollars,
                RoomRates.quetzales,
                RoomTypes.room_name,
            )
            #the calendar already says if a date is week, wknd or peak
            .join(RoomRates, RoomRates.time_of_the_week == Calendar.time_of_the_week)
            .join(RoomTypes, RoomTypes.room_code == RoomRates.room_code)
            .where(
                RoomRates.room_code == room_code,
                Calendar.calendar_date >= check_in,
                Calendar.calendar_date < check_out,
            )
            .order_by(Calendar.calendar_date)
        )
        rows = session.execute(query).all()

        name_of_room = "No se encontro la habitacion"
        total_points = 0
        total_dollars = 0
        total_quetzales = 0
        nights_detail = []
        for row in rows:
            name_of_room = row.room_name
            quetzales = row.quetzales
            total_points = total_points + row.points
            total_dollars = total_dollars + row.dollars
            total_quetzales = total_quetzales + quetzales
            nights_detail.append({
                "night": row.calendar_date,
                "time_of_the_week": row.time_of_the_week,
                "points": row.points,
                "dollars": row.dollars,
                "quetzales": quetzales,
            })

    return {
        "room": name_of_room,
        "total_points": total_points,
        "total_dollars": total_dollars,
        "total_quetzales": total_quetzales,
        "nights": nights_detail,
    }

def get_quote(room_code, check_in, check_out):
    points = get_room_points(room_code, check_in, check_out)

    return {
        "room": points["room"],
        "total_points": points["total_points"],
        "dollars": points["total_dollars"],
        "quetzales": points["total_quetzales"]
    }




def get_room_combinations(hotel, adults, kids):
    with PgSession() as session:
        query = (
            select(
                RoomCombinations.combination_type,
                RoomCombinations.priority,
                RoomCombinations.room_code,
                RoomCombinations.quantity,
                RoomTypes.room_name,
            )
            .join(RoomTypes, RoomTypes.room_code == RoomCombinations.room_code)
            .where(
                RoomCombinations.hotel == hotel,
                RoomCombinations.adults == adults,
                RoomCombinations.kids == kids,
                RoomCombinations.active.is_(True),
            )
            .order_by(RoomCombinations.priority, RoomCombinations.combination_type)
        )
        rows = session.execute(query).all()

        #every row sharing a combination_type is one offer, two rooms means two rows
        options = {}
        for row in rows:
            if row.combination_type not in options:
                options[row.combination_type] = {
                    "option_id": row.combination_type,
                    "priority": row.priority,
                    "rooms": [],
                }
            options[row.combination_type]["rooms"].append({
                "room_code": row.room_code,
                "room_name": row.room_name,
                "quantity": row.quantity,
            })

        combinations = []
        for option_id in options:
            combinations.append(options[option_id])
        return combinations


def get_allotments_within_stay(session, hotel_id, room, check_in, check_out):
    query = (
        select(Allotments, RoomTypes)
        .join(RoomTypes, Allotments.room_code == RoomTypes.room_code)
        .where(
            Allotments.hotel == hotel_id,
            RoomTypes.hotel == hotel_id,
            RoomTypes.room_code == room,
            Allotments.availability == "DISPONIBLE",
            Allotments.check_in >= check_in,
            Allotments.check_out <= check_out,
        )
    )
    return session.execute(query).all()


def count_free_units_per_night(rows, check_in, check_out):
    number_of_nights = (check_out - check_in).days

    free_units_per_night = {}
    for night_number in range(number_of_nights):
        one_night = check_in + timedelta(days=night_number)
        free_units_per_night[one_night] = 0

    for allotment, room_type in rows:
        for one_night in free_units_per_night:
            if allotment.check_in <= one_night and allotment.check_out > one_night:
                free_units_per_night[one_night] = free_units_per_night[one_night] + 1

    return free_units_per_night


def smallest_free_units(free_units_per_night):
    counts = list(free_units_per_night.values())
    if counts == []:
        return 0

    smallest = counts[0]
    for count in counts:
        if count < smallest:
            smallest = count
    return smallest


def check_availability(hotel, room, check_in, check_out):
    with PgSession() as session:
        rows = get_allotments_within_stay(session, hotel, room, check_in, check_out)

        free_units_per_night = count_free_units_per_night(rows, check_in, check_out)
        units_free_for_whole_stay = smallest_free_units(free_units_per_night)
        available = units_free_for_whole_stay > 0

        room_name = ""
        for allotment, room_type in rows:
            room_name = room_type.room_name

        nights_detail = []
        for one_night in free_units_per_night:
            nights_detail.append({
                "night": one_night,
                "free_units": free_units_per_night[one_night],
            })

        return {
            "available": available,
            "room": room_name,
            "check_in": check_in,
            "check_out": check_out,
            "units_free_for_whole_stay": units_free_for_whole_stay,
            "nights": nights_detail,
        }

def get_next_available_dates(room_name):
    with PgSession() as session:
        query = (
            select(Allotments, RoomTypes)
            .join(
                RoomTypes,
                (Allotments.room_code == RoomTypes.room_code)
                & (Allotments.hotel == RoomTypes.hotel),
            )
            .where(
                RoomTypes.hotel.in_(["antigua", "pacifico"]),
                #like so a partial name still matches the stored name
                RoomTypes.room_name.like("%" + room_name + "%"),
                Allotments.availability == "DISPONIBLE",
                Allotments.check_in >= date.today(),
            )
            .order_by(Allotments.check_in)
        )
        rows = session.execute(query).all()

        next_available_dates = []
        for allotment, room_type in rows:
            next_available_dates.append({
                "hotel": allotment.hotel,
                "code": allotment.room_code,
                "room": room_type.room_name,
                "check_in": allotment.check_in,
                "check_out": allotment.check_out,
            })
        return next_available_dates

def get_bookable_hotels_and_rooms():
    with PgSession() as session:
        #room_types only holds the rooms we sell, so nothing needs filtering out
        query = (
            select(RoomTypes)
            .order_by(RoomTypes.hotel, RoomTypes.room_code)
        )
        rows = session.scalars(query).all()

        catalog = []
        for room_type in rows:
            room_name = room_type.room_name.strip()
            catalog.append({
                "hotel": room_type.hotel,
                "room_id": room_type.room_code,
                "room_name": room_name,
            })
        return catalog


def is_member(membership_number):
    with PgSession() as session:
        query = (
            select(Members.membership_number)
            .where(Members.membership_number == membership_number)
        )
        result = session.scalar(query)
        if result is None:
            return False
        else:
            return True

def get_member_points(membership_number):
    with PgSession() as session:
        session.execute(
            text("CALL actualizarCuenta(:membership_number)"),
            {"membership_number": membership_number},
        )
        session.commit()

        query = (
            select(Members.available_points)
            .where(Members.membership_number == membership_number)
        )
        available_points = session.scalar(query)
        return available_points

def conversation_exists(conversation_id):
    with PgSession() as session:
        query = select(Conversation.id).where(
            Conversation.external_user_id == conversation_id
        )
        return session.scalar(query) is not None


def create_conversation(conversation_id):
    with PgSession() as session:
        conversation = Conversation(external_user_id=conversation_id)
        session.add(conversation)
        session.commit()


def save_message(conversation_id, role, message):
    with PgSession() as session:
        internal_id = session.scalar(
            select(Conversation.id).where(
                Conversation.external_user_id == conversation_id
            )
        )
        new_message = Message(
            conversation_id=internal_id,
            role=role,
            content=message,
        )
        session.add(new_message)
        session.commit()


def load_history(conversation_id):
    with PgSession() as session:
        query = (
            select(Message)
            .join(Conversation, Message.conversation_id == Conversation.id)
            .where(Conversation.external_user_id == conversation_id)
            .order_by(Message.created_at)
        )
        rows = session.scalars(query).all()

        history = []
        for row in rows:
            history.append({"role": row.role, "content": row.content})
        return history

def actualizar_cuenta(contract_number):
    with MySQLSession() as mysql_session:
        mysql_session.execute(text("call actualizarCuenta(:junto)"),
                              {"junto": contract_number})
        mysql_session.commit()
        row = mysql_session.execute(text("""
            select PUNCOM, PUNTOS_PAGADOS, PUNCON, PUNENC, PUNTOS_DISPONIBLES, pbot, pbun
            from pasante
            where JUNTO = :junto
        """), {"junto": contract_number}).mappings().first()

    if row is None:
        return None

    with PgSession() as pg_session:
        pg_session.execute(
            update(Points)
            .where(Points.contract_number == contract_number)
            .values(
                points_per_contract=row["PUNCOM"],
                points_paid_for=row["PUNTOS_PAGADOS"],
                points_used=row["PUNCON"],
                points_expired=row["PUNENC"],
                points_available=row["PUNTOS_DISPONIBLES"],
                bono_granted=row["pbot"],
                bono_used=row["pbun"],
            )
        )
        pg_session.commit()

    return row["PUNTOS_DISPONIBLES"]





############OPUS CAN ONLY ADD BELOW HERE. IF NEEDED COMMENT OUT FUNCTIONS ABOVE
