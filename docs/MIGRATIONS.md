# Database Migrations (Alembic)

Retention Core v3.0 has moved from a custom DuckDB/SQLite hybrid migration runner to a unified **PostgreSQL** schema managed by **Alembic**.

## Architecture
- All models are defined in `models.py` using SQLAlchemy 2.0.
- Alembic generates migration scripts by comparing `models.Base.metadata` to the live Postgres database.
- On application boot (`app.py`), `alembic upgrade head` is automatically executed to ensure the schema is up-to-date.

## Creating a new migration

When you modify, add, or delete any models in `models.py`, you must generate a new migration script:

1. Ensure your local Postgres database is running via Docker:
   ```bash
   docker-compose up -d postgres
   ```
2. Generate the migration script:
   ```bash
   python -m alembic revision --autogenerate -m "Add new feature X"
   ```
3. Review the generated script in `alembic/versions/` to ensure Alembic didn't miss anything (like custom indexes or complex constraints).
4. Apply the migration locally (optional, since it will run automatically on the next app boot):
   ```bash
   python -m alembic upgrade head
   ```

## Downgrading

To roll back the last migration:
```bash
python -m alembic downgrade -1
```

To roll back everything:
```bash
python -m alembic downgrade base
```
