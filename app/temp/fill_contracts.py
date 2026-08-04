from sqlalchemy import text

from app.database import MySQLSession, PgSession

BATCH_SIZE = 1000

ACTIVE_STATUS = "ACTIVO"

FIELDS = [
    ("membership_number", "NUMCON"),
    ("contract_date", "FECCON"),
    ("original_purchase_date", "compra_original"),
    ("contract_price", "PRECIO"),
    ("original_contract_price", "valor_original"),
    ("down_payment_agreed", "paen_original"),
    ("down_payment_fees", "OTROS"),
    ("down_payment_total_due", "TOEN"),
    ("down_payment_paid", "PAEN"),
    ("financed_principal", "TOCA"),
    ("financed_principal_paid", "PACA"),
    ("capital_pending", "PECA"),
    ("interest_total", "toin"),
    ("interest_paid", "PAIN"),
    ("interest_outstanding", "PEIN"),
    ("annual_interest_rate_percent", "tasanu"),
    ("percent_paid", "PORPAG"),
    ("previous_contract_number", "JUNTO_ANT"),
    ("next_contract_number", "JUNTO_SIG"),
    ("installments_total", "TOPE"),
    ("installments_pending", "PEPE"),
    ("installments_overdue", "VEPE"),
    ("monthly_payment", "CU"),
    ("capital_overdue", "VECA"),
    ("interest_overdue", "VEIN"),
    ("first_payment_date", "FECPRI"),
    ("cancellation_date", "FECCAN"),
    ("contract_term_years", "POR"),
    ("credit_balance", "saldofav"),
    ("expiration_date", "fecven"),
]

DATE_SOURCES = {"FECCON", "compra_original", "FECPRI", "FECCAN", "fecven"}


def clean_date(value):
    if value is None:
        return None
    if str(value).startswith("0000-00-00"):
        return None
    return value


def clean_text(value):
    if value is None:
        return None
    cleaned = str(value).strip()
    if cleaned == "":
        return None
    return cleaned


def read_active_contracts(session):
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
        if origin in DATE_SOURCES:
            row[target] = clean_date(source[origin])
        else:
            row[target] = source[origin]
    return row


def build_statement():
    targets = ["contract_number"] + [target for target, _ in FIELDS]
    columns = ", ".join(targets)
    placeholders = ", ".join(f":{target}" for target in targets)
    assignments = ", ".join(f"{target} = excluded.{target}" for target, _ in FIELDS)
    return text(
        f"insert into contracts ({columns}) values ({placeholders}) "
        f"on conflict (contract_number) do update set {assignments}"
    )


def fill_contracts():
    statement = build_statement()
    written = 0
    missing_source = 0
    without_purchase_date = 0

    with MySQLSession() as mysql_session, PgSession() as pg_session:
        by_junto = read_active_contracts(mysql_session)
        contract_numbers = [
            row[0]
            for row in pg_session.execute(
                text("select contract_number from members")
            ).all()
        ]

        rows = []
        for contract_number in contract_numbers:
            source = by_junto.get(contract_number)
            if source is None:
                missing_source = missing_source + 1
                continue

            row = build_row(contract_number, source)
            if row["original_purchase_date"] is None:
                without_purchase_date = without_purchase_date + 1
                continue

            rows.append(row)

            if len(rows) == BATCH_SIZE:
                pg_session.execute(statement, rows)
                written = written + len(rows)
                rows = []

        if rows:
            pg_session.execute(statement, rows)
            written = written + len(rows)

        pg_session.commit()

    print(f"members {len(contract_numbers)}")
    print(f"written {written}")
    print(f"missing source {missing_source}")
    print(f"without purchase date {without_purchase_date}")
    return {
        "written": written,
        "missing_source": missing_source,
        "without_purchase_date": without_purchase_date,
    }


if __name__ == "__main__":
    fill_contracts()
