from collections.abc import Generator
from contextlib import contextmanager

import psycopg
from psycopg import Connection

from app.config import settings


@contextmanager
def get_db_connection() -> Generator[Connection, None, None]:
    """
    Create and close a PostgreSQL database connection.

    This is intentionally kept in the db layer so routes do not directly
    manage database connection details.
    """
    connection = psycopg.connect(settings.database_url, connect_timeout=3)

    try:
        yield connection
    finally:
        connection.close()


def check_database_connection() -> bool:
    """
    Check whether PostgreSQL is reachable.

    SELECT 1 is used because it does not require any application tables.
    This is useful before the database schema exists.
    """
    with get_db_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            result = cursor.fetchone()

    return result == (1,)
