from app.db.schema_guard import ensure_schema
from app.queue.worker import process_sla_monitor


def main() -> int:
    ensure_schema()
    updated = process_sla_monitor()
    return int(updated or 0)


if __name__ == "__main__":
    raise SystemExit(main())
