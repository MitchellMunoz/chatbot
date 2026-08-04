from datetime import datetime, timezone

from sqlalchemy import select, text, update
from sqlalchemy.dialects.postgresql import insert

from app.database import MySQLSession, PgSession
from app.models import Members, Points

ACTIVE_STATUS = "ACTIVO"

BATCH_SIZE = 500

MEMBER_COLUMNS = [
    "available_points",
    "paid_points",
    "contract_price_synced_at",
]

POINTS_FIELDS = [
    ("points_per_contract", "PUNCOM"),
    ("points_paid_for", "PUNTOS_PAGADOS"),
    ("points_used", "PUNCON"),
    ("points_expired", "PUNENC"),
    ("points_available", "PUNTOS_DISPONIBLES"),
    ("bono_granted", "pbot"),
    ("bono_used", "pbun"),
]

SOURCE_COLUMNS = ["JUNTO", "PUNTOS_DISPONIBLES", "PUNTOS_PAGADOS", "PUNCOM",
                  "PUNCON", "PUNENC", "pbot", "pbun"]


def clean_text(value):
    if value is None:
        return None
    cleaned = str(value).strip()
    if cleaned == "":
        return None
    return cleaned


def read_contract_numbers(session):
    query = text("""
        select JUNTO from pasante
        where ESTATUS = :status
        order by JUNTO
    """)

    numbers = []
    for row in session.execute(query, {"status": ACTIVE_STATUS}).all():
        junto = clean_text(row[0])
        if junto is not None:
            numbers.append(junto)
    return numbers


def refresh_accounts(session):
    refreshed = 0
    failed = 0

    for contract_number in read_contract_numbers(session):
        try:
            session.execute(text("call actualizarCuenta(:contrato)"),
                            {"contrato": contract_number})
            session.commit()
            refreshed = refreshed + 1
        except Exception:
            session.rollback()
            failed = failed + 1

    return refreshed, failed


def read_points(session):
    columns = ", ".join(SOURCE_COLUMNS)
    query = text(f"select {columns} from pasante where ESTATUS = :status")

    by_junto = {}
    for row in session.execute(query, {"status": ACTIVE_STATUS}).mappings().all():
        junto = clean_text(row["JUNTO"])
        if junto is not None:
            by_junto[junto] = row
    return by_junto


def read_one_contract(session, contract_number):
    columns = ", ".join(SOURCE_COLUMNS)
    query = text(f"select {columns} from pasante where JUNTO = :junto and ESTATUS = :status")
    return session.execute(
        query, {"junto": contract_number, "status": ACTIVE_STATUS}
    ).mappings().first()


def build_member_row(contract_number, source, synced_at):
    return {
        "contract_number": contract_number,
        "available_points": source["PUNTOS_DISPONIBLES"],
        "paid_points": source["PUNTOS_PAGADOS"],
        "contract_price_synced_at": synced_at,
    }


def build_points_row(contract_number, source):
    row = {"contract_number": contract_number}
    for target, origin in POINTS_FIELDS:
        row[target] = source[origin]
    return row


def write_members(session, rows):
    session.execute(update(Members), rows)
    return len(rows)


def write_points_table(session, rows):
    statement = insert(Points).values(rows)
    statement = statement.on_conflict_do_update(
        index_elements=[Points.contract_number],
        set_={target: statement.excluded[target] for target, _ in POINTS_FIELDS},
    )
    session.execute(statement)
    return len(rows)


def update_contract_points(contract_number):
    synced_at = datetime.now(timezone.utc)
    contract_number = clean_text(contract_number)
    if contract_number is None:
        return {"contract_number": None, "status": "no contract number given"}

    with MySQLSession() as mysql_session:
        mysql_session.execute(text("call actualizarCuenta(:contrato)"),
                              {"contrato": contract_number})
        mysql_session.commit()
        source = read_one_contract(mysql_session, contract_number)

    if source is None:
        return {"contract_number": contract_number, "status": "not active in pasante"}

    with PgSession() as pg_session:
        stored = pg_session.scalar(
            select(Members.contract_number).where(Members.contract_number == contract_number)
        )
        if stored is None:
            return {"contract_number": contract_number, "status": "no members row"}

        write_members(pg_session, [build_member_row(contract_number, source, synced_at)])
        write_points_table(pg_session, [build_points_row(contract_number, source)])
        pg_session.commit()

    result = build_points_row(contract_number, source)
    result["status"] = "updated"
    return result


def update_points():
    synced_at = datetime.now(timezone.utc)

    with MySQLSession() as mysql_session:
        refreshed, failed = refresh_accounts(mysql_session)
        by_junto = read_points(mysql_session)

    members_written = 0
    points_written = 0
    without_source = 0

    with PgSession() as pg_session:
        contract_numbers = pg_session.scalars(select(Members.contract_number)).all()

        member_rows = []
        points_rows = []
        for contract_number in contract_numbers:
            source = by_junto.get(contract_number)
            if source is None:
                without_source = without_source + 1
                continue

            member_rows.append(build_member_row(contract_number, source, synced_at))
            points_rows.append(build_points_row(contract_number, source))

            if len(member_rows) == BATCH_SIZE:
                members_written = members_written + write_members(pg_session, member_rows)
                points_written = points_written + write_points_table(pg_session, points_rows)
                member_rows = []
                points_rows = []

        if member_rows:
            members_written = members_written + write_members(pg_session, member_rows)
            points_written = points_written + write_points_table(pg_session, points_rows)

        pg_session.commit()

    return {
        "refreshed": refreshed,
        "refresh_failed": failed,
        "members_written": members_written,
        "points_written": points_written,
        "without_source": without_source,
    }


if __name__ == "__main__":
    now = datetime.now(timezone.utc)
    result = update_points()
    print(f"{now.isoformat(timespec='seconds')} {result}")
