import os
import re
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv
from sqlalchemy import select, update

from app.database import PgSession
from app.models import Members

load_dotenv()

BATCH_SIZE = 500

REQUEST_TIMEOUT = 60

VISA_CODES = {
    "Posee": True,
    "No Posee": False,
}

PASSPORT_DOCUMENT_TYPE = "EXT"

DPI_PATTERN = re.compile(r"[0-9]{13}")

COUNTRY_SUFFIX = " GUATEMALA"

ACCENT_REPLACEMENTS = {
    "Á": "A",
    "É": "E",
    "Í": "I",
    "Ó": "O",
    "Ú": "U",
    "Ñ": "N",
}

DEPARTMENT_NAMES = [
    "Alta Verapaz",
    "Baja Verapaz",
    "Chimaltenango",
    "Chiquimula",
    "El Progreso",
    "Escuintla",
    "Guatemala",
    "Huehuetenango",
    "Izabal",
    "Jalapa",
    "Jutiapa",
    "Peten",
    "Quetzaltenango",
    "Quiche",
    "Retalhuleu",
    "Sacatepequez",
    "San Marcos",
    "Santa Rosa",
    "Solola",
    "Suchitepequez",
    "Totonicapan",
    "Zacapa",
]

WIDTHS = {
    "phone": 20,
    "city": 60,
    "department": 80,
    "country": 40,
    "nationality": 40,
    "age": 3,
    "income": 30,
    "passport": 40,
}

UPDATED_COLUMNS = [
    "phone",
    "city",
    "department",
    "country",
    "nationality",
    "age",
    "income",
    "visa",
    "passport",
    "dpi",
    "birth_date",
    "updated_at",
]

CONTRACT_QUERY = """
    SELECT Numero_completo__c, AccountId
    FROM Contract
    WHERE Numero_completo__c != null AND AccountId != null
"""

ACCOUNT_QUERY = """
    SELECT Id, Phone, BillingCity, BillingState, BillingCountry, Departamento__pc,
           Nacionalidad__pc, Edad__pc, Ingresos__pc, Visa__pc,
           Tipo_de_documento__pc, Numero_de_documento__pc, PersonBirthdate
    FROM Account
    WHERE IsPersonAccount = true
"""


def connect_salesforce():
    response = requests.post(
        os.getenv("URL_SALESFORCE_TOKEN"),
        data={
            "grant_type": os.getenv("SALESFORCE_GRANT_TYPE"),
            "client_id": os.getenv("CLIENT_ID_SALESFORCE"),
            "client_secret": os.getenv("CLIENT_SECRET_SALESFORCE"),
        },
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()

    session = requests.Session()
    session.headers.update({"Authorization": "Bearer " + response.json()["access_token"]})

    instance = os.getenv("ENDPOINT_SALESFORCE").rstrip("/")
    version = os.getenv("CLIENT_VERSION_SALESFORCE").lstrip("v")
    return session, instance, instance + "/services/data/v" + version


def query_salesforce(session, instance, base, soql):
    rows = []
    response = session.get(base + "/query", params={"q": soql}, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    payload = response.json()
    rows.extend(payload["records"])

    while not payload.get("done"):
        response = session.get(instance + payload["nextRecordsUrl"], timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        payload = response.json()
        rows.extend(payload["records"])

    return rows


def clean_text(value):
    if value is None:
        return None
    cleaned = str(value).strip()
    if cleaned == "":
        return None
    return cleaned


def fit(column, value):
    if value is None:
        return None
    if len(value) > WIDTHS[column]:
        return None
    return value


def normalize_department(value):
    key = value.strip().upper()
    for accented, plain in ACCENT_REPLACEMENTS.items():
        key = key.replace(accented, plain)
    if key.endswith(COUNTRY_SUFFIX):
        key = key[: -len(COUNTRY_SUFFIX)].strip()
    if key.startswith("EL "):
        key = key[3:].strip()
    return key


DEPARTMENT_BY_KEY = {}
for department_name in DEPARTMENT_NAMES:
    DEPARTMENT_BY_KEY[normalize_department(department_name)] = department_name


def read_department(account):
    raw = clean_text(account.get("Departamento__pc"))
    if raw is None:
        raw = clean_text(account.get("BillingState"))
    if raw is None:
        return None
    return DEPARTMENT_BY_KEY.get(normalize_department(raw))


def read_age(account):
    age = account.get("Edad__pc")
    if age is None:
        return None
    return str(int(age))


def read_visa(account):
    visa = clean_text(account.get("Visa__pc"))
    if visa is None:
        return None
    return VISA_CODES.get(visa)


def read_passport(account):
    document_type = clean_text(account.get("Tipo_de_documento__pc"))
    if document_type != PASSPORT_DOCUMENT_TYPE:
        return None
    return clean_text(account.get("Numero_de_documento__pc"))


def read_dpi(account):
    dpi = clean_text(account.get("Numero_de_documento__pc"))
    if dpi is None:
        return None
    if DPI_PATTERN.fullmatch(dpi):
        return dpi
    return None


def read_birth_date(account):
    return clean_text(account.get("PersonBirthdate"))


def keep_existing(existing, found):
    if existing is not None:
        return existing
    return found


def build_row(contract_number, account, existing, synced_at):
    return {
        "contract_number": contract_number,
        "dpi": keep_existing(existing["dpi"], read_dpi(account)),
        "birth_date": keep_existing(
            existing["birth_date"], read_birth_date(account)
        ),
        "phone": fit("phone", clean_text(account.get("Phone"))),
        "city": fit("city", clean_text(account.get("BillingCity"))),
        "department": fit("department", read_department(account)),
        "country": fit("country", clean_text(account.get("BillingCountry"))),
        "nationality": fit("nationality", clean_text(account.get("Nacionalidad__pc"))),
        "age": fit("age", read_age(account)),
        "income": fit("income", clean_text(account.get("Ingresos__pc"))),
        "visa": read_visa(account),
        "passport": fit("passport", read_passport(account)),
        "updated_at": synced_at,
    }


def has_any_value(row):
    for column in UPDATED_COLUMNS:
        if column == "updated_at":
            continue
        if row[column] is not None:
            return True
    return False


def update_members(session, rows):
    session.execute(update(Members), rows)
    return len(rows)


def sync_members_salesforce():
    synced_at = datetime.now(timezone.utc)
    session, instance, base = connect_salesforce()

    account_by_contract = {}
    for contract in query_salesforce(session, instance, base, CONTRACT_QUERY):
        key = clean_text(contract["Numero_completo__c"])
        if key is not None:
            account_by_contract[key] = contract["AccountId"]

    accounts = {}
    for account in query_salesforce(session, instance, base, ACCOUNT_QUERY):
        accounts[account["Id"]] = account

    matched = 0
    written = 0
    without_contract = 0
    without_account = 0
    empty = 0

    with PgSession() as pg_session:
        stored = pg_session.execute(
            select(Members.contract_number, Members.dpi, Members.birth_date)
        ).all()

        existing_by_contract = {}
        for contract_number, dpi, birth_date in stored:
            existing_by_contract[contract_number] = {
                "dpi": dpi,
                "birth_date": birth_date,
            }

        contract_numbers = list(existing_by_contract)

        rows = []
        for contract_number in contract_numbers:
            account_id = account_by_contract.get(contract_number)
            if account_id is None:
                without_contract = without_contract + 1
                continue

            account = accounts.get(account_id)
            if account is None:
                without_account = without_account + 1
                continue

            matched = matched + 1
            row = build_row(
                contract_number, account, existing_by_contract[contract_number], synced_at
            )
            if not has_any_value(row):
                empty = empty + 1
                continue

            rows.append(row)

            if len(rows) == BATCH_SIZE:
                written = written + update_members(pg_session, rows)
                rows = []

        if rows:
            written = written + update_members(pg_session, rows)

        pg_session.commit()

    return {
        "members": len(contract_numbers),
        "matched": matched,
        "written": written,
        "without_contract": without_contract,
        "without_account": without_account,
        "empty": empty,
    }


if __name__ == "__main__":
    now = datetime.now(timezone.utc)
    result = sync_members_salesforce()
    print(f"{now.isoformat(timespec='seconds')} {result}")
