from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert

from app.database import MySQLSession, PgSession
from app.models import Members, Points

BATCH_SIZE = 1000

ACTIVE_STATUS = "ACTIVO"

FIELDS = [
    ("points_per_contract", "PUNCOM"),
    ("points_paid_for", "PUNTOS_PAGADOS"),
    ("points_used", "PUNCON"),
    ("points_expired", "PUNENC"),
    ("points_available", "PUNTOS_DISPONIBLES"),
    ("bono_granted", "PBOT"),
    ("bono_used", "PBUN"),
]


def clean_text(value):
    if value is None:
        return None
    cleaned = str(value).strip()
    if cleaned == "":
        return None
    return cleaned


def read_active_points(session):
    columns = ", ".join(["JUNTO"] + [source for _, source in FIELDS])
    query = text(f"select {columns} from pasante where ESTATUS = :status")

    by_junto = {}
    for row in session.execute(query, {"status": ACTIVE_STATUS}).mappings().all():
        junto = clean_text(row["JUNTO"])
        if junto is not None:
            by_junto[junto] = row
    return by_junto


def build_row(contract_number, source):
    row = {"contract_number": contract_number}
    for target, origin in FIELDS:
        row[target] = source[origin]
    return row


def upsert_points(session, rows):
    statement = insert(Points).values(rows)
    statement = statement.on_conflict_do_update(
        index_elements=[Points.contract_number],
        set_={target: statement.excluded[target] for target, _ in FIELDS},
    )
    session.execute(statement)
    return len(rows)


def fill_points():
    written = 0
    missing_source = 0

    with MySQLSession() as mysql_session, PgSession() as pg_session:
        by_junto = read_active_points(mysql_session)
        contract_numbers = pg_session.scalars(select(Members.contract_number)).all()

        rows = []
        for contract_number in contract_numbers:
            source = by_junto.get(contract_number)
            if source is None:
                missing_source = missing_source + 1
                continue

            rows.append(build_row(contract_number, source))

            if len(rows) == BATCH_SIZE:
                written = written + upsert_points(pg_session, rows)
                rows = []

        if rows:
            written = written + upsert_points(pg_session, rows)

        pg_session.commit()

    print(f"members {len(contract_numbers)}")
    print(f"written {written}")
    print(f"missing source {missing_source}")
    return {"written": written, "missing_source": missing_source}


if __name__ == "__main__":
    fill_points()
