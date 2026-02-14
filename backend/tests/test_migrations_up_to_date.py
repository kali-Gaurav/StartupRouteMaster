from alembic.config import Config
from alembic import command
from alembic.migration import MigrationContext
from alembic.autogenerate import compare_metadata
from backend.database import engine, Base


def test_models_and_migrations_are_in_sync():
    """Fail the test when SQLAlchemy models and Alembic migrations are out-of-sync.

    Strategy:
    1. Apply repository migrations to the test database (alembic upgrade head).
    2. Use Alembic's `compare_metadata` to compare the live DB schema vs SQLAlchemy `Base.metadata`.
    3. Fail when `compare_metadata` returns any diffs (i.e. model changes without migrations).
    """
    cfg = Config("backend/alembic.ini")

    # Ensure the DB schema is at the repository head
    command.upgrade(cfg, "head")

    # Compare DB (migrations) with current model metadata
    with engine.connect() as conn:
        mc = MigrationContext.configure(conn)
        diffs = compare_metadata(mc, Base.metadata)

    assert not diffs, (
        "Detected model <-> migration mismatch. Run `alembic revision --autogenerate` "
        "and commit the generated migration before merging. Diffs: {}".format(diffs)
    )
