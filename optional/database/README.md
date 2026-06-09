# Database (optional)

Off by default. Set `SPARK_DATABASE_ON=true` in `.env`.

- `database_operations.py` — SQLite persistence for user-defined instruction libraries

Imported by `actions/actions.py` only when `SPARK_DATABASE_ON` is enabled.
