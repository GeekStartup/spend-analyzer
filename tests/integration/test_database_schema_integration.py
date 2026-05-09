from decimal import Decimal
from uuid import uuid4

import pytest
from psycopg import IntegrityError

from app.db.connection import get_db_connection


@pytest.mark.integration
def test_flyway_migrations_were_applied():
    expected_migrations = {
        ("1", "enable pgcrypto"),
        ("2", "create statements table"),
        ("3", "create transactions table"),
    }

    with get_db_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT version, description
                FROM flyway_schema_history
                WHERE success = true
                ORDER BY installed_rank
                """
            )

            actual_migrations = set(cursor.fetchall())

    assert expected_migrations.issubset(actual_migrations)


@pytest.mark.integration
def test_schema_creates_statement_and_transaction_tables():
    with get_db_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_name IN ('statements', 'transactions')
                ORDER BY table_name
                """
            )

            table_names = [row[0] for row in cursor.fetchall()]

    assert table_names == ["statements", "transactions"]


@pytest.mark.integration
def test_sample_statement_and_transaction_can_be_inserted_and_queried():
    user_id = f"user-{uuid4()}"

    with get_db_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO statements (
                    user_id,
                    account_name,
                    statement_type,
                    original_file_name,
                    stored_file_path,
                    status
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    user_id,
                    "HDFC Millennia Credit Card",
                    "credit_card",
                    "hdfc-millennia-may-2026.pdf",
                    "/app/uploads/hdfc-millennia-may-2026.pdf",
                    "uploaded",
                ),
            )

            statement_row = cursor.fetchone()
            assert statement_row is not None
            statement_id = statement_row[0]

            cursor.execute(
                """
                INSERT INTO transactions (
                    user_id,
                    statement_id,
                    transaction_date,
                    description,
                    merchant,
                    category,
                    amount,
                    transaction_type,
                    account_name
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    user_id,
                    statement_id,
                    "2026-05-01",
                    "SWIGGY BANGALORE",
                    "Swiggy",
                    "Food",
                    Decimal("425.50"),
                    "debit",
                    "HDFC Millennia Credit Card",
                ),
            )

            transaction_row = cursor.fetchone()
            assert transaction_row is not None
            transaction_id = transaction_row[0]

            cursor.execute(
                """
                SELECT
                    t.id,
                    t.user_id,
                    t.merchant,
                    t.category,
                    t.amount,
                    t.transaction_type,
                    s.original_file_name
                FROM transactions t
                JOIN statements s
                  ON s.id = t.statement_id
                 AND s.user_id = t.user_id
                WHERE t.id = %s
                  AND t.user_id = %s
                """,
                (transaction_id, user_id),
            )

            result_row = cursor.fetchone()

        connection.commit()

    assert result_row is not None
    assert result_row[0] == transaction_id
    assert result_row[1] == user_id
    assert result_row[2] == "Swiggy"
    assert result_row[3] == "Food"
    assert result_row[4] == Decimal("425.50")
    assert result_row[5] == "debit"
    assert result_row[6] == "hdfc-millennia-may-2026.pdf"


@pytest.mark.integration
def test_transaction_cannot_reference_another_users_statement():
    statement_owner_user_id = f"user-{uuid4()}"
    different_user_id = f"user-{uuid4()}"

    with get_db_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO statements (
                    user_id,
                    account_name,
                    statement_type,
                    original_file_name,
                    stored_file_path,
                    status
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    statement_owner_user_id,
                    "Axis Savings Account",
                    "savings_account",
                    "axis-savings-may-2026.pdf",
                    "/app/uploads/axis-savings-may-2026.pdf",
                    "uploaded",
                ),
            )

            statement_row = cursor.fetchone()
            assert statement_row is not None
            statement_id = statement_row[0]

            with pytest.raises(IntegrityError):
                cursor.execute(
                    """
                    INSERT INTO transactions (
                        user_id,
                        statement_id,
                        transaction_date,
                        description,
                        merchant,
                        category,
                        amount,
                        transaction_type,
                        account_name
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        different_user_id,
                        statement_id,
                        "2026-05-01",
                        "NEFT CREDIT",
                        "Unknown",
                        "Transfer",
                        Decimal("1000.00"),
                        "credit",
                        "Axis Savings Account",
                    ),
                )

        connection.rollback()


@pytest.mark.integration
def test_common_query_indexes_exist():
    expected_indexes = {
        "idx_statements_user_uploaded_at",
        "idx_statements_user_status",
        "idx_transactions_user_date",
        "idx_transactions_user_category",
        "idx_transactions_user_merchant",
        "idx_transactions_statement_id",
    }

    with get_db_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT indexname
                FROM pg_indexes
                WHERE schemaname = 'public'
                  AND indexname = ANY(%s)
                """,
                (list(expected_indexes),),
            )

            actual_indexes = {row[0] for row in cursor.fetchall()}

    assert actual_indexes == expected_indexes
