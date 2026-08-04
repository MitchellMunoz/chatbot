from datetime import datetime, timezone

from app.scripts.quetzales_db import update_quetzales


if __name__ == "__main__":
    now = datetime.now(timezone.utc)
    result = update_quetzales()
    print(f"{now.isoformat(timespec='seconds')} {result}")
