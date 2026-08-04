from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from app.queries import get_room_combinations, check_availability, get_quote, get_bookable_hotels_and_rooms, get_next_available_dates, is_member
from app.scripts.reach_browser import reach_login
try:
    from zoneinfo import ZoneInfo

    GT = ZoneInfo("America/Guatemala")
except Exception:
    GT = timezone(timedelta(hours=-6))

def write_error_log(tool_name, tool_input, error_message):
    errors_folder = Path("app/errors")
    errors_folder.mkdir(parents=True, exist_ok=True)

    today_text = date.today().isoformat()
    log_file_path = errors_folder / f"{today_text}.log"

    now = datetime.now(GT)
    time_text = now.strftime("%Y-%m-%d %H:%M:%S")

    log_line = f"{time_text} | tool={tool_name} | input={tool_input} | error={error_message}\n"

    with open(log_file_path, "a", encoding="utf-8") as log_file:
        log_file.write(log_line)


TOOLS = [
    {
        "name": "reach_login",
        "description": (
            "Abre https://app.reach.tools/v5/login en un navegador, escribe el usuario y la contrasena, "
            "y presiona el boton de Login. Devuelve logged_in true cuando la sesion se abrio, "
            "junto con la url y el titulo de la pagina donde quedo. "
            "No recibe parametros: el usuario y la contrasena salen del servidor, nunca del socio."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "is_member",
        "description": (
            "Check whether a membership number is real, by looking it up in the live members database right now. "
            "Call this as soon as the member gives you their membership number, before checking availability, before quoting, and before preparing any reservation request. "
            "The result is true when the membership number exists and false when it does not. If it is false, tell the member the number was not found and ask them to confirm it. If it is false a second time, tell them you are transferring them to the credits department so they can verify their membership number, and do not continue with the reservation."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "membership_number": {
                    "type": "string",
                    "description": "The membership number exactly as the member gave it, with no characters added or removed. It is 5 digits, for example '27528' or '11838'. It never contains letters. Do not pad with zeros and do not reformat the number.",
                },
            },
            "required": ["membership_number"],
        },
    },
    {
        "name": "list_hotels_and_rooms",
        "description": (
            "Return the current, authoritative list of hotels and room types this bot can book, read directly from the database. "
            "Each entry has hotel (use this exact value in the 'hotel' field of check_availability and get_room_combinations), room_id (use this exact value in the 'room' field of check_availability and get_quote), and room_name. "
            "Call this tool whenever the member's hotel or room wording is unclear, misspelled, abbreviated, or does not confidently and exactly match a known option, so you can compare their wording against the real list and either match it with confidence or show them the real options and ask which one they mean. "
            "Do NOT guess a hotel or room from a partial, misspelled, or ambiguous name without calling this tool first. "
            "This tool only tells you what hotels and room types exist. It never tells you whether a room is available on any date or what it costs. Knowing a room exists is not the same as knowing it is free; you must still call check_availability or get_quote separately before saying anything about availability or price."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "check_availability",
        "description": (
            "Check whether a specific room type is actually free at one of our two hotels for an exact date range, by querying the live reservations database right now. "
            "This is the only source of truth for availability. Never state, confirm, or imply that a room is available based on the system prompt, on your own knowledge, or on something said earlier in this conversation. "
            "Call this tool every single time a member asks about availability for a room and dates, even if you already checked the same room and dates earlier in this same conversation, because inventory can change between messages. "
            "Read the answer from the 'available' field: true means the room can be booked for the whole stay, false means it cannot. 'units_free_for_whole_stay' is how many units of this room type are free for the entire stay; if the member needs more than one unit of this room (for example 2 Dobles), that number must be at least that many. The 'nights' list shows the free units night by night. "
            "The result of this call is what you must tell the member. If a member insists a room was available a moment ago and you are not sure that is still true, call this tool again and report the current result instead of trusting what was said earlier."
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
                    "enum": ["D2DLA", "D2DLP", "V1BR", "V2BR", "B1BR", "B2BR", "D2JSE", "STE", "STL"],
                    "description": "The room code. Each code belongs to exactly one hotel. Antigua: D2DLA (Doble), V1BR (Villa de 4), V2BR (Villa de 6). Pacifico: D2DLP (Doble), B1BR (Bungalo de 4), B2BR (Bungalo de 6), D2JSE (Mini Suite), STE (Suite Estandar), STL (Suite de Lujo). If the member's wording does not clearly map to one of these, call list_hotels_and_rooms first instead of guessing.",
                },
                "check_in": {
                    "type": "string",
                    "description": "The check_in date resolved to ISO format YYYY-MM-DD. Resolve relative dates like 'mañana' or 'this thursday' using today's date from the system prompt. If the resolved date could plausibly fall in more than one year, confirm the year with the member before calling this tool.",
                },
                "check_out": {
                    "type": "string",
                    "description": "The check_out date resolved to ISO format YYYY-MM-DD. Resolve relative dates like 'mañana' or 'this thursday' using today's date from the system prompt. If the resolved date could plausibly fall in more than one year, confirm the year with the member before calling this tool.",
                },
            },
            "required": ["hotel", "room", "check_in", "check_out"],
        },
    },
    {
        "name": "get_next_available_dates",
        "description": (
            "Find the next dates a room type is actually free, by querying the live reservations database right now. "
            "Use this when a member asks when a room is available but has NOT given exact check-in and check-out dates, for example 'cuando hay Bungalo de 4' or 'que fechas tiene libre la Suite de Lujo'. "
            "It takes only the room name, matches it against the real room names in the database, and returns the upcoming available date ranges starting from today, soonest first. If the name exists at both hotels, results for both hotels are returned. "
            "Each entry has hotel (antigua or pacifico), code, room, check_in, and check_out. An empty list means there are no upcoming available dates for that room name. "
            "If the member already gave exact dates, call check_availability instead. This tool does not price anything; call get_quote before telling the member a price."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "room_name": {
                    "type": "string",
                    "description": "The room name as the member said it, for example 'Bungalo de 4' or 'Suite de Lujo'. A partial name is fine; it is matched against the real room names in the database. If the member's wording is unclear or misspelled, call list_hotels_and_rooms first and use the room_name from there.",
                },
            },
            "required": ["room_name"],
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
        "description": (
            "Calculate the official quote for a specific room, hotel, and date range, by querying the live points chart and the current daily exchange rate in the database right now. "
            "The result already contains total_points, dollars, and quetzales fully calculated. Read these numbers directly from the tool result and report them to the member exactly as returned. Do not recompute them, do not convert between currencies yourself, and do not reuse an exchange rate or total you saw earlier in the conversation. "
            "Call this tool every time a member asks for a price or total, even if you quoted the same room and dates earlier in this conversation, because the exchange rate can change day to day. "
            "This tool does not check availability. Confirm availability with check_availability for the same room and dates before presenting this quote as something the member can book."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "room": {
                    "type": "string",
                    "enum": ["D2DLA", "D2DLP", "V1BR", "V2BR", "B1BR", "B2BR", "D2JSE", "STE", "STL"],
                    "description": "The room code. Each code belongs to exactly one hotel. Antigua: D2DLA (Doble), V1BR (Villa de 4), V2BR (Villa de 6). Pacifico: D2DLP (Doble), B1BR (Bungalo de 4), B2BR (Bungalo de 6), D2JSE (Mini Suite), STE (Suite Estandar), STL (Suite de Lujo). If the member's wording does not clearly map to one of these, call list_hotels_and_rooms first instead of guessing.",
                },
                "check_in": {
                    "type": "string",
                    "description": "The check_in date resolved to ISO format YYYY-MM-DD. Resolve relative dates like 'mañana' or 'this thursday' using today's date from the system prompt. If the resolved date could plausibly fall in more than one year, confirm the year with the member before calling this tool.",
                },
                "check_out": {
                    "type": "string",
                    "description": "The check_out date resolved to ISO format YYYY-MM-DD. Resolve relative dates like 'mañana' or 'this thursday' using today's date from the system prompt. If the resolved date could plausibly fall in more than one year, confirm the year with the member before calling this tool.",
                },
            },
            "required": ["room", "check_in", "check_out"],
        },
    },
]

def run_tool(name, tool_input):
    try:
        if name == "is_member":
            membership_number = tool_input["membership_number"]
            member_found = is_member(membership_number)
            return{"is_member": member_found}

        if name == "reach_login":
            return reach_login()
        if name == "list_hotels_and_rooms":
            catalog = get_bookable_hotels_and_rooms()
            return {"hotels_and_rooms": catalog}

        if name == "get_room_combinations":
            hotel = tool_input["hotel"]
            adults = tool_input["adults"]
            children = tool_input["children"]

            options = get_room_combinations(hotel, adults, children)
            return {"options": options}

        if name == "check_availability":
            hotel = tool_input["hotel"]
            room = tool_input["room"]
            check_in_text = tool_input["check_in"]
            check_out_text = tool_input["check_out"]

            try:
                check_in_date = date.fromisoformat(check_in_text)
                check_out_date = date.fromisoformat(check_out_text)
            except ValueError:
                error_message = "Dates must be in ISO format YYYY-MM-DD."
                write_error_log(name, tool_input, error_message)
                return {"error": error_message}

            availability = check_availability(hotel, room, check_in_date, check_out_date)
            return availability

        if name == "get_next_available_dates":
            room_name = tool_input["room_name"]
            next_available_dates = get_next_available_dates(room_name)
            return {"next_available_dates": next_available_dates}

        if name == "get_quote":
            room = tool_input["room"]
            check_in_text = tool_input["check_in"]
            check_out_text = tool_input["check_out"]

            try:
                check_in_date = date.fromisoformat(check_in_text)
                check_out_date = date.fromisoformat(check_out_text)
            except ValueError:
                error_message = "Dates must be in ISO format YYYY-MM-DD."
                write_error_log(name, tool_input, error_message)
                return {"error": error_message}

            quote = get_quote(room, check_in_date, check_out_date)
            return quote

        error_message = f"Unknown tool: {name}"
        write_error_log(name, tool_input, error_message)
        return {"error": error_message}
    except Exception as error:
        error_message = f"Tool {name} failed: {error}"
        write_error_log(name, tool_input, error_message)
        return {"error": error_message}

def current_datetime_guatemala():
    dias = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
    meses = [
        "enero", "febrero", "marzo", "abril", "mayo", "junio",
        "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
    ]
    now = datetime.now(GT)
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
