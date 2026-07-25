from datetime import date, datetime, timedelta, timezone
from sqlalchemy import text
from app.queries import get_room_combinations, check_availability
try:
    from zoneinfo import ZoneInfo

    GUATEMALA_TZ = ZoneInfo("America/Guatemala")
except Exception: 
    GUATEMALA_TZ = timezone(timedelta(hours=-6))

HOTEL_NAME_TO_ID = {
    "antigua": 1,
    "pacifico": 2,
}


TOOLS = [
    {
        "name": "check_availability",
        "description": (
            "Check whether a specific room type is available at a hotel for a given date range for a customer. Use this before calling get_quote. Anytime a customer asks for availability to stay at one of our two hotels, you must first use this tool to check the database to see if there is any space."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "hotel": {
                    "type": "string",
                    "enum": ["antigua", "pacifico"],
                    "description": "which hotel to check.",
                },
                "room": {
                    "type": "string",
                    "description": "The type of room at the hotel.",
                },
                "check_in": {
                    "type": "string",
                    "description": "The check_in date resolved to ISO format YYYY-MM-DD. Resolve relative dates like 'mañana' or 'this thursday' using today's date from the system prompt.",
                },
                "check_out": {
                    "type": "string",
                    "description": "The check_out date resolved to ISO format YYYY-MM-DD. Resolve relative dates like 'mañana' or 'this thursday' using today's date from the system prompt.",
                },
            },
            "required": ["hotel", "room", "check_in", "check_out"],
        },
    },
    {
        "name": "get_room_combinations",
        "description": (
            "Given a hotel and the exact number of adults and children in the party, return the room configurations Club Premier can offer for that party size. Each returned option may be a single room or a bundle of several rooms, and the options are ordered by priority (offer the first ones first). After calling this tool you MUST call check_availability for every room listed in each option, and only offer the member the options whose rooms are ALL available for the requested dates."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "hotel": {
                    "type": "string",
                    "enum": ["antigua", "pacifico"],
                    "description": "Which hotel to search room combinations for.",
                },
                "adults": {
                    "type": "integer",
                    "description": "Number of adults in the party.",
                },
                "children": {
                    "type": "integer",
                    "description": "Number of children in the party.",
                },
            },
            "required": ["hotel", "adults", "children"],
        },
    },
    {
        "name": "get_quote",
        "description": "Calculate the hotel quote based on the users requests and the information in the MYSQL database. You will multiply the dollar value by 7.5 to get the value in quetzales.",
        "input_schema": {
            "type": "object",
            "properties": {
                "hotel": {"type": "string", "description": "The name of the hotel."},
                "room": {
                    "type": "string",
                    "description": "The type of room at the hotel.",
                },
                "check_in": {
                    "type": "string",
                    "description": "The check_in date resolved to ISO format YYYY-MM-DD. Resolve relative dates like 'mañana' or 'this thursday' using today's date from the system prompt.",
                },
                "check_out": {
                    "type": "string",
                    "description": "he check_out date resolved to ISO format YYYY-MM-DD. Resolve relative dates like 'mañana' or 'this thursday' using today's date from the system prompt.",
                },
            },
            "required": ["hotel", "room", "check_in", "check_out"],
        },
    },
]

def run_tool(name, tool_input):
    try:
        if name == "get_room_combinations":
            hotel = tool_input["hotel"]
            adults = tool_input["adults"]
            children = tool_input["children"]

            rows = get_room_combinations(hotel_id, adults, children)

            options = {}
            for combination, detail, unit in rows:
                if combination.id not in options:
                    options[combination.id] = {
                        "option_id": combination.id,
                        "priority": combination.priority,
                        "rooms": [],
                    }
                options[combination.id]["rooms"].append({
                    "room_code": unit.code,
                    "room_name": unit.room,
                    "quantity": detail.quantity,
                })

            result = []
            for option_id in options:
                result.append(options[option_id])
            return {"options": result}

        if name == "check_availability":
            hotel = tool_input["hotel"]
            room = tool_input["room"]
            check_in_text = tool_input["check_in"]
            check_out_text = tool_input["check_out"]

            try:
                check_in_date = date.fromisoformat(check_in_text)
                check_out_date = date.fromisoformat(check_out_text)
            except ValueError:
                return {"error": "Dates must be in ISO format YYYY-MM-DD."}

            available_rooms = check_availability(hotel, room, check_in_date, check_out_date)
            return {"available_rooms": available_rooms}

        if name == "get_quote":
            return {"error": "get_quote is not implemented yet."}

        return {"error": f"Unknown tool: {name}"}
    except Exception as error:
        return {"error": f"Tool {name} failed: {error}"}

def current_datetime_guatemala():
    dias = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
    meses = [
        "enero", "febrero", "marzo", "abril", "mayo", "junio",
        "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
    ]
    now = datetime.now(GUATEMALA_TZ)
    return {
        "iso": now.isoformat(timespec="seconds"),
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M"),
        "year": now.year,
        "weekday": dias[now.weekday()],
        "human_es": (
            f"{dias[now.weekday()]} {now.day} de {meses[now.month - 1]} "
            f"de {now.year}, {now.strftime('%H:%M')} (hora de Guatemala)"
        ),
        "timezone": "America/Guatemala (UTC-6)",
    }


def current_datetime_text():
    return current_datetime_guatemala()["human_es"]
