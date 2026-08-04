from datetime import date, datetime, timezone
from sqlalchemy import bindparam, text, update
from app.database import PgSession
from app.scripts.exchange_rate_api import get_exchange_rates
from app.models import Calendar

#banguat does not publish on weekends or holidays, those days keep the last rate
FILL_PAST_GAPS = text("""
    UPDATE calendar
    SET exchange_rate = (
        SELECT previous.exchange_rate
        FROM calendar AS previous
        WHERE previous.exchange_rate IS NOT NULL
          AND previous.date < calendar.date
        ORDER BY previous.date DESC
        LIMIT 1
    )
    WHERE exchange_rate IS NULL
      AND date <= CURRENT_DATE
""")


def update_exchange_rates(session, rows):
    #the calendar row already exists for every date, so this only fills a column.
    #it updates the table and not the orm class, the orm path wants an id per row
    statement = (
        update(Calendar.__table__)
        .where(Calendar.calendar_date == bindparam("target_date"))
        .values(exchange_rate=bindparam("rate"))
    )
    session.execute(statement, rows)
    return len(rows)


def carry_forward_exchange_rate(session):
    return session.execute(FILL_PAST_GAPS).rowcount


def sync_exchange_rate(rate_date=None):
    if rate_date is None:
        rate_date = date.today()

    #asking for a single day is the same call with both ends on that date
    rates = get_exchange_rates(rate_date, rate_date)

    rows = []
    for rate in rates:
        rows.append({
            "target_date": rate["date"],
            "rate": rate["venta"],
        })

    written = 0
    with PgSession() as session:
        if rows:
            written = update_exchange_rates(session, rows)
        carried = carry_forward_exchange_rate(session)
        session.commit()

    #banguat publishes nothing on weekends and holidays, so read can be 0
    return {"date": rate_date, "read": len(rates), "written": written, "carried": carried}


if __name__ == "__main__":
    now = datetime.now(timezone.utc)
    result = sync_exchange_rate()
    print(f"{now.isoformat(timespec='seconds')} {result}")
