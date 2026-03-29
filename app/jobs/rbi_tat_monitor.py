from app.db.schema_guard import ensure_schema
from app.queue.worker import process_rbi_monthly_reports, process_rbi_tat_monitor


def main() -> int:
    ensure_schema()
    updated = int(process_rbi_tat_monitor() or 0)
    generated = int(process_rbi_monthly_reports() or 0)
    return updated + generated


if __name__ == "__main__":
    raise SystemExit(main())
