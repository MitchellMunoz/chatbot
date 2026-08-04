import re
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert

from app.database import MySQLSession, PgSession
from app.models import Members

BATCH_SIZE = 1000

ACTIVE_STATUS = "ACTIVO"

SHORTEST_CONTRACT_NUMBER = 5

ADDRESS_WIDTH = 90

POSTAL_CODE_WIDTH = 8

PHONE_WIDTH = 20

EMAIL_WIDTH = 60

DPI_PATTERN = re.compile(r"[0-9]{13}")

NIT_PATTERN = re.compile(r"[0-9]+")

PASANTE_COLUMNS = [
    "JUNTO",
    "NUMCON",
    "ESTATUS",
    "DPI",
    "NIT",
    "fecnac",
    "OCUPACION",
]

CONDIR_COLUMNS = [
    "JUNTO",
    "CORR",
    "FECHA",
    "DIRECC1",
    "DIRECC2",
    "CODPOS",
    "TELCAS",
    "TELOFI",
    "MAIL",
]

UPDATED_COLUMNS = [
    "membership_number",
    "is_active",
    "email",
    "address",
    "postal_code",
    "dpi",
    "nit",
    "birth_date",
    "profesion",
    "home_phone",
    "office_phone",
    "updated_at",
]


def clean_text(value):
    if value is None:
        return None
    cleaned = str(value).strip()
    if cleaned == "":
        return None
    return cleaned


def clean_date(value):
    if value is None:
        return None
    if str(value).startswith("0000-00-00"):
        return None
    return value


def clean_dpi(value):
    dpi = clean_text(value)
    if dpi is None:
        return None
    if DPI_PATTERN.fullmatch(dpi):
        return dpi
    return None


def clean_nit(value):
    nit = clean_text(value)
    if nit is None:
        return None
    if NIT_PATTERN.fullmatch(nit):
        return nit
    return None


def fit(value, width):
    if value is None:
        return None
    if len(value) > width:
        return None
    return value


def condir_order(row):
    return (str(row["FECHA"] or ""), row["CORR"])


def read_active_rows(session):
    columns = ", ".join(PASANTE_COLUMNS)
    query = text(f"select {columns} from pasante where ESTATUS = :status")
    return session.execute(query, {"status": ACTIVE_STATUS}).mappings().all()


def read_contacts(session):
    columns = ", ".join(CONDIR_COLUMNS)
    query = text(f"select {columns} from condir")

    latest_by_junto = {}
    for row in session.execute(query).mappings().all():
        junto = clean_text(row["JUNTO"])
        if junto is None:
            continue
        current = latest_by_junto.get(junto)
        if current is None or condir_order(row) > condir_order(current):
            latest_by_junto[junto] = row
    return latest_by_junto


def read_address(contact):
    first_line = clean_text(contact["DIRECC1"])
    second_line = clean_text(contact["DIRECC2"])

    if first_line is None:
        return fit(second_line, ADDRESS_WIDTH)
    if second_line is None:
        return fit(first_line, ADDRESS_WIDTH)

    combined = first_line + " " + second_line
    if len(combined) <= ADDRESS_WIDTH:
        return combined
    return fit(first_line, ADDRESS_WIDTH)


def build_row(source, contact, synced_at):
    membership_number = source["NUMCON"]
    if membership_number is not None:
        membership_number = str(membership_number)

    row = {
        "contract_number": clean_text(source["JUNTO"]),
        "membership_number": membership_number,
        "is_active": clean_text(source["ESTATUS"]),
        "email": None,
        "address": None,
        "postal_code": None,
        "dpi": clean_dpi(source["DPI"]),
        "nit": clean_nit(source["NIT"]),
        "birth_date": clean_date(source["fecnac"]),
        "profesion": clean_text(source["OCUPACION"]),
        "home_phone": None,
        "office_phone": None,
        "updated_at": synced_at,
    }

    if contact is not None:
        row["email"] = fit(clean_text(contact["MAIL"]), EMAIL_WIDTH)
        row["address"] = read_address(contact)
        row["postal_code"] = fit(clean_text(contact["CODPOS"]), POSTAL_CODE_WIDTH)
        row["home_phone"] = fit(clean_text(contact["TELCAS"]), PHONE_WIDTH)
        row["office_phone"] = fit(clean_text(contact["TELOFI"]), PHONE_WIDTH)

    return row


def upsert_members(session, rows):
    statement = insert(Members).values(rows)
    statement = statement.on_conflict_do_update(
        index_elements=[Members.contract_number],
        set_={column: statement.excluded[column] for column in UPDATED_COLUMNS},
    )
    session.execute(statement)
    return len(rows)


def sync_members():
    synced_at = datetime.now(timezone.utc)
    read = 0
    written = 0
    skipped = 0
    without_contact = 0
    without_dpi = 0

    with MySQLSession() as mysql_session, PgSession() as pg_session:
        contacts = read_contacts(mysql_session)
        sources = read_active_rows(mysql_session)

        rows = []
        seen_contract_numbers = set()
        seen_membership_numbers = set()

        for source in sources:
            read = read + 1
            contract_number = clean_text(source["JUNTO"])

            if contract_number is None:
                skipped = skipped + 1
                continue
            if len(contract_number) < SHORTEST_CONTRACT_NUMBER:
                skipped = skipped + 1
                continue
            if contract_number in seen_contract_numbers:
                skipped = skipped + 1
                continue

            contact = contacts.get(contract_number)
            if contact is None:
                without_contact = without_contact + 1

            row = build_row(source, contact, synced_at)

            membership_number = row["membership_number"]
            if membership_number in seen_membership_numbers:
                row["membership_number"] = None
            else:
                seen_membership_numbers.add(membership_number)

            seen_contract_numbers.add(contract_number)

            if row["dpi"] is None:
                without_dpi = without_dpi + 1

            rows.append(row)

            if len(rows) == BATCH_SIZE:
                written = written + upsert_members(pg_session, rows)
                rows = []

        if rows:
            written = written + upsert_members(pg_session, rows)

        pg_session.commit()

    return {
        "read": read,
        "written": written,
        "skipped": skipped,
        "without_contact": without_contact,
        "without_dpi": without_dpi,
    }


if __name__ == "__main__":
    now = datetime.now(timezone.utc)
    result = sync_members()
    print(f"{now.isoformat(timespec='seconds')} {result}")
