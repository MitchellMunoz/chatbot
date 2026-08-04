from app.database import MySQLSession, PgSession
from sqlalchemy import text

FIELDS = [
    ("primary_account_holder", "NOMBRE1"),
    ("secondary_account_holder", "NOMBRE2"),
    ("status", "ESTATUS"),
    ("cancellation_type", "TIPCAN"),
    ("program", "programa"),
    ("birth_date", "fecnac"),
    ("email", "MAIL"),
    ("home_phone", "telcas"),
    ("office_phone", "telofi"),
    ("dpi", "DPI"),
    ("nit", "NIT"),
    ("billing_name", "nitnombre"),
    ("address", "DIREC"),
    ("postal_code", "codpos"),
    ("available_points", "PUNTOS_DISPONIBLES"),
    ("paid_points", "PUNTOS_PAGADOS"),
]


def clean(value):
    if value is None:
        return None
    if str(value).startswith("0000-00-00"):
        return None
    return value


def clean_cancellation_type(value):
    if value is None:
        return None
    if value.strip() == "":
        return "active"
    return value.strip()


def load_pasante():
    columns = ", ".join(["JUNTO", "NUMCON", "TIPCAN"] + [source for _, source in FIELDS])
    by_junto = {}
    by_numcon = {}
    with MySQLSession() as session:
        rows = session.execute(text(f"select {columns} from pasante")).mappings().all()
    for row in rows:
        by_junto[row["JUNTO"]] = row
        key = str(row["NUMCON"])
        if row["TIPCAN"] == "":
            by_numcon.setdefault(key, []).append(row)
    return by_junto, by_numcon


def fill_members():
    by_junto, by_numcon = load_pasante()
    assignments = ", ".join(f"{target} = :{target}" for target, _ in FIELDS)
    updated = 0
    linked = 0
    skipped = 0
    with PgSession() as session:
        members = session.execute(
            text("select membership_number, contract_number from members")
        ).all()
        for membership_number, contract_number in members:
            source = None
            new_contract_number = None
            if contract_number:
                source = by_junto.get(contract_number)
            else:
                candidates = by_numcon.get(membership_number, [])
                if len(candidates) == 1:
                    source = candidates[0]
                    new_contract_number = source["JUNTO"]
            if source is None:
                skipped += 1
                continue
            params = {target: clean(source[origin]) for target, origin in FIELDS}
            params["cancellation_type"] = clean_cancellation_type(source["TIPCAN"])
            params["membership_number"] = membership_number
            statement = f"update members set {assignments}, updated_at = now()"
            if new_contract_number:
                statement += ", contract_number = :contract_number"
                params["contract_number"] = new_contract_number
                linked += 1
            statement += " where membership_number = :membership_number"
            session.execute(text(statement), params)
            updated += 1
        session.commit()
    print(f"updated {updated}, newly linked {linked}, skipped {skipped}")
