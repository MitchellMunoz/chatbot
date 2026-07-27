from uuid import UUID
from sqlalchemy import select
from sqlalchemy.orm import Session
from datetime import date 
from app.database import PgSession, MySQLSession
from app.models import Conversation, Message, Combination, Detail, Unit_type, Allotment, Destination, SeasonCalendar, ExchangeRate


from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

GT = ZoneInfo("America/Guatemala")
now = datetime.now(GT)

HOTEL_NAME_TO_ID = {
    "antigua": 1,
    "pacifico": 2,
}

HOTEL_ID_TO_SLUG = {
    1: "antigua",
    2: "pacifico",
}

HOTEL_ID_TO_NAME = {
    1: "Soleil La Antigua",
    2: "Soleil Pacífico",
}

BOOKABLE_ROOM_IDS = ["D2DL", "V1BR", "V2BR", "B1BR", "B2BR", "D2JSE", "STE", "STL"]

#Find out if the day is a weekend
#Monday is 0
def get_hotel_name(room_id):
    with MySQLSession() as session:
        query =(
            #hotel = 1 or 2
        select (Unit_type.room_id, Unit_type.hotel_id, Unit_type.room_name)
        .where (Unit_type.room_id == room_id))
        row = session.execute(query).all()
        # list = []
        # for r in row:
        #     list.append(r)
        #return list
        return row


def is_friday_or_saturday(check_in_out):
    the_number_of_the_day = check_in_out.weekday()
    if the_number_of_the_day == 4 or the_number_of_the_day == 5:
        return True
    else:
        return False


def get_points(hotel_id, room_id, year):

    with MySQLSession() as session:
        query = (
            select(Destination, Unit_type)
            #only rows that match both room_id and hotel_id, so room codes
            #that repeat at other hotels in this shared database do not match
            .join(
                Unit_type,
                
                (Unit_type.room_id == Destination.room_id)
                #where 1 = antigua 
                & (Unit_type.hotel_id == Destination.hotel_id),
            )
            .where(
                #where the room_id differs from user input, then drop row
                Destination.room_id == room_id,
                #if user input is 1, it drops pacifico rows
                Destination.hotel_id == hotel_id,
                Destination.points > 0, #no rows with 0 points
                Destination.year == year #only rows for the check-in year
            )
            )
        
        rows = session.execute(query).all()
        #if the for loop finds a value, it will overwrite the value in room_name
        name_of_room = "No se encontro la habitacion"
        points_by_day = {}
        #loop through the results in the query above
        for dest, unit_type in rows:
            name_of_room = unit_type.room_name
            points_by_day[dest.day] = dest.points
    
    return {
        "room": name_of_room,
        "points_by_day": points_by_day,
    }

def points_for_one_night(one_night, points_by_day):
    # Friday and Saturday nights are charged the weekend rate
    if is_friday_or_saturday(one_night):
        return points_by_day["FIN"]
    # every other night is charged the weekday rate
    else:
        return points_by_day["ENTRE"]
#get the list of points a room chargesa



def get_quote(hotel_id, room_id, check_in, check_out):
    with MySQLSession() as session:
        exchange_rate = get_exchange_rate(session)
        points = get_points(hotel_id, room_id, check_in.year)
        room_name = points["room"]
        points_by_day = points["points_by_day"]

        number_of_nights = (check_out - check_in).days
        total_points = 0
        for nights in range(number_of_nights):
            one_night = check_in + timedelta(days=nights)
            total_points = total_points + points_for_one_night(one_night, points_by_day)
        dollars = total_points * 4.5
        quetzales = dollars * exchange_rate
    return {
        "room": room_name,
        "total_points": total_points,
        "dollars": dollars,
        "quetzales": quetzales
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
                Unit_type)
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


def get_allotments_within_stay(session, hotel_id, room, check_in, check_out):
    query = (
        select(Allotment, Unit_type)
        .join(Unit_type, Allotment.room_id == Unit_type.room_id)
        .where(
            Allotment.hotel_id == hotel_id,
            Unit_type.hotel_id == hotel_id,
            Unit_type.room_id == room,
            Allotment.estado == "DISPONIBLE",
            Allotment.check_in >= check_in,
            Allotment.check_out <= check_out,
        )
    )
    return session.execute(query).all()


def count_free_units_per_night(rows, check_in, check_out):
    number_of_nights = (check_out - check_in).days

    free_units_per_night = {}
    for night_number in range(number_of_nights):
        one_night = check_in + timedelta(days=night_number)
        free_units_per_night[one_night] = 0

    for allotment, unit_type in rows:
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
    hotel = HOTEL_NAME_TO_ID[hotel]
    with MySQLSession() as session:
        rows = get_allotments_within_stay(session, hotel, room, check_in, check_out)

        free_units_per_night = count_free_units_per_night(rows, check_in, check_out)
        units_free_for_whole_stay = smallest_free_units(free_units_per_night)
        available = units_free_for_whole_stay > 0

        room_name = ""
        for allotment, unit_type in rows:
            room_name = unit_type.room_name

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
    with MySQLSession() as session:
        query = (
            select(Allotment, Unit_type)
            .join(
                Unit_type,
                (Allotment.room_id == Unit_type.room_id)
                & (Allotment.hotel_id == Unit_type.hotel_id),
            )
            .where(
                Unit_type.hotel_id.in_([1, 2]),
                #like so a partial name still matches the stored name
                Unit_type.room_name.like("%" + room_name + "%"),
                Allotment.estado == "DISPONIBLE",
                Allotment.check_in >= date.today(),
            )
            .order_by(Allotment.check_in)
        )
        rows = session.execute(query).all()

        next_available_dates = []
        for allotment, unit_type in rows:
            next_available_dates.append({
                "hotel": allotment.hotel_id,
                "code": allotment.room_id,
                "room": unit_type.room_name,
                "check_in": allotment.check_in,
                "check_out": allotment.check_out,
            })
        return next_available_dates

def get_exchange_rate(session):
    query = (
        select(ExchangeRate.rate)
        .where(ExchangeRate.today <= date.today())
        .order_by(ExchangeRate.today.desc())
    )
    return session.scalars(query).first()

def get_bookable_hotels_and_rooms():
    with MySQLSession() as session:
        query = (
            select(Unit_type)
            .where(
                Unit_type.hotel_id.in_([1, 2]),
                Unit_type.room_id.in_(BOOKABLE_ROOM_IDS),
            )
            .order_by(Unit_type.hotel_id, Unit_type.room_id)
        )
        rows = session.scalars(query).all()

        catalog = []
        for unit in rows:
            hotel_slug = HOTEL_ID_TO_SLUG[unit.hotel_id]
            hotel_name = HOTEL_ID_TO_NAME[unit.hotel_id]
            room_name = unit.room_name.strip()
            catalog.append({
                "hotel_id": unit.hotel_id,
                "hotel_slug": hotel_slug,
                "hotel_name": hotel_name,
                "room_id": unit.room_id,
                "room_name": room_name,
            })
        return catalog