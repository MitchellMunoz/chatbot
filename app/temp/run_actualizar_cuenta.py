from sqlalchemy import text

from app.database import MySQLSession

ACTIVE_STATUS = "ACTIVO"

REPORT_EVERY = 100


def read_contract_numbers(session, only_missing):
    query = "select JUNTO from pasante where ESTATUS = :status"
    if only_missing:
        query = query + " and PUNTOS_DISPONIBLES is null"
    query = query + " order by JUNTO"

    numbers = []
    for row in session.execute(text(query), {"status": ACTIVE_STATUS}).all():
        junto = row[0]
        if junto is not None and str(junto).strip() != "":
            numbers.append(str(junto).strip())
    return numbers


def run_actualizar_cuenta(limit=None, only_missing=True):
    done = 0
    failed = 0
    failures = []

    with MySQLSession() as session:
        numbers = read_contract_numbers(session, only_missing)
        if limit is not None:
            numbers = numbers[:limit]

        print(f"contracts to process {len(numbers)}")

        for contract_number in numbers:
            try:
                session.execute(text("call actualizarCuenta(:contrato)"),
                                {"contrato": contract_number})
                session.commit()
                done = done + 1
            except Exception as error:
                session.rollback()
                failed = failed + 1
                failures.append((contract_number, str(error)[:120]))

            if done % REPORT_EVERY == 0 and done > 0:
                print(f"  processed {done} of {len(numbers)}")

    print(f"done {done}")
    print(f"failed {failed}")
    for contract_number, message in failures[:10]:
        print(f"  {contract_number} {message}")

    return {"done": done, "failed": failed, "failures": failures}


if __name__ == "__main__":
    run_actualizar_cuenta()
