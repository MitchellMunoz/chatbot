from datetime import date, datetime, timedelta, timezone
from sqlalchemy import func, or_, select
from sqlalchemy.dialects.postgresql import insert
from app.database import MySQLSession, PgSession
from app.models import Allotments, RoomTypes
from app.mysql import Allotment

BATCH_SIZE = 2000

LOOKBACK_DAYS = 3

HOTEL_ID_TO_SLUG = {
    1: "antigua",
    2: "pacifico",
}

D2DL_TO_ROOM_CODE = {
    1: "D2DLA",
    2: "D2DLP",
}

BOOKABLE_ROOM_CODES = ["D2DL", "V1BR", "V2BR", "B1BR", "B2BR", "D2JSE", "STE", "STL"]

UPDATED_COLUMNS = ["hotel", "room_code", "check_in", "check_out", "availability",
                   "program", "membership_number", "quote", "online", "synced_at"]


def resolve_room_code(room_code, hotel):
    #d2dl is the only code both hotels share, so it needs the hotel to split
    if room_code == "D2DL":
        return D2DL_TO_ROOM_CODE[hotel]
    else:
        return room_code


def get_room_codes(session):
    query = select(RoomTypes.room_code)
    return set(session.scalars(query).all())


def get_last_synced_id(session):
    query = select(func.max(Allotments.id))
    last_synced_id = session.scalar(query)
    if last_synced_id is None:
        return 0
    else:
        return last_synced_id


def get_changed_allotments(session, last_synced_id, full):
    modified_since = date.today() - timedelta(days=LOOKBACK_DAYS)

    changed = [
        Allotment.id > last_synced_id,
        Allotment.modified_on >= modified_since,
    ]
    if full:
        #about 4900 rows never got a MODIFICA, an edit to one is invisible above
        changed.append(Allotment.modified_on.is_(None))

    query = (
        select(Allotment)
        .where(
            Allotment.program == "PTS",
            Allotment.hotel.in_([1, 2]),
            Allotment.room_code.in_(BOOKABLE_ROOM_CODES),
            or_(*changed),
        )
        .order_by(Allotment.id)
        .execution_options(yield_per=BATCH_SIZE)
    )
    return session.scalars(query)


def upsert_allotments(session, rows):
    statement = insert(Allotments).values(rows)
    statement = statement.on_conflict_do_update(
        index_elements=[Allotments.id],
        set_={column: statement.excluded[column] for column in UPDATED_COLUMNS},
    )
    session.execute(statement)
    return len(rows)


def delete_missing_allotments(mysql_session, pg_session):
    #mysql leaves no tombstone, the id lists have to be compared to see a delete
    query = (
        select(Allotment.id)
        .where(
            Allotment.program == "PTS",
            Allotment.hotel.in_([1, 2]),
            Allotment.room_code.in_(BOOKABLE_ROOM_CODES),
        )
    )
    live_ids = set(mysql_session.scalars(query).all())
    stored_ids = set(pg_session.scalars(select(Allotments.id)).all())

    gone_ids = stored_ids - live_ids
    if not gone_ids:
        return 0

    pg_session.execute(Allotments.__table__.delete().where(Allotments.id.in_(gone_ids)))
    return len(gone_ids)


def sync_allotments(full=False):
    synced_at = datetime.now(timezone.utc)
    read = 0
    written = 0
    deleted = 0
    unmapped = {}

    with MySQLSession() as mysql_session, PgSession() as pg_session:
        room_codes = get_room_codes(pg_session)
        last_synced_id = get_last_synced_id(pg_session)

        rows = []
        for allotment in get_changed_allotments(mysql_session, last_synced_id, full):
            read = read + 1
            room_code = resolve_room_code(allotment.room_code, allotment.hotel)

            #room_types changed under us, the foreign key would reject the row
            if room_code not in room_codes:
                unmapped[allotment.room_code] = unmapped.get(allotment.room_code, 0) + 1
                continue
            online = allotment.online.strip()
            if online == "":
                online = None

            rows.append({
                "id": allotment.id,
                "hotel": HOTEL_ID_TO_SLUG[allotment.hotel],
                "room_code": room_code,
                "check_in": allotment.check_in,
                "check_out": allotment.check_out,
                "availability": allotment.availability,
                "program": allotment.program,
                "membership_number": allotment.membership_number,
                "quote": allotment.quote,
                "online": online,
                "synced_at": synced_at,
            })

            if len(rows) == BATCH_SIZE:
                written = written + upsert_allotments(pg_session, rows)
                rows = []

        if rows:
            written = written + upsert_allotments(pg_session, rows)

        if full:
            deleted = delete_missing_allotments(mysql_session, pg_session)

        pg_session.commit()

    return {
        "read": read,
        "written": written,
        "deleted": deleted,
        "unmapped": unmapped,
    }


if __name__ == "__main__":
    now = datetime.now(timezone.utc)
    full = now.hour == 8 and now.minute < 15
    result = sync_allotments(full=full)
    print(f"{now.isoformat(timespec='seconds')} full={full} {result}")
