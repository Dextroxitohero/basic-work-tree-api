"""Tests unitarios del cursor: sin HTTP y sin base de datos."""

from datetime import UTC, date, datetime
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.core.pagination import (
    InvalidCursorError,
    SortSpec,
    contains_pattern,
    decode_cursor,
    encode_cursor,
    parse_aware_datetime,
)
from app.modules.employees.models import Employee

BY_NAME = SortSpec("last_name", Employee.last_name)
BY_DATE = SortSpec("hire_date", Employee.hire_date, date.fromisoformat)
BY_CREATED = SortSpec("created_at", Employee.created_at, parse_aware_datetime)


def test_cursor_round_trip_keeps_value_and_id():
    row_id = uuid4()
    moment = datetime(2024, 5, 1, 10, 30, 15, 123456, tzinfo=UTC)

    name_cursor = encode_cursor(BY_NAME, "asc", "García", row_id)
    date_cursor = encode_cursor(BY_DATE, "desc", date(2020, 1, 31), row_id)
    moment_cursor = encode_cursor(BY_CREATED, "asc", moment, row_id)

    assert decode_cursor(name_cursor, BY_NAME, "asc") == ("García", row_id)
    assert decode_cursor(date_cursor, BY_DATE, "desc") == (date(2020, 1, 31), row_id)
    assert decode_cursor(moment_cursor, BY_CREATED, "asc") == (moment, row_id)


def test_cursor_is_url_safe():
    cursor = encode_cursor(BY_NAME, "asc", "¿ñandú?>>", uuid4())

    assert cursor.isascii()
    assert not set(cursor) & set("+/= ")


@pytest.mark.parametrize(
    "cursor",
    [
        "no-es-un-cursor",
        "",
        "e30",  # "{}": falta todo
        "WzEsMl0",  # "[1,2]": no es un objeto
    ],
)
def test_malformed_cursor_is_rejected(cursor):
    with pytest.raises(InvalidCursorError):
        decode_cursor(cursor, BY_NAME, "asc")


def test_cursor_of_another_sort_or_order_is_rejected():
    cursor = encode_cursor(BY_NAME, "asc", "García", uuid4())

    with pytest.raises(InvalidCursorError):
        decode_cursor(cursor, BY_DATE, "asc")
    with pytest.raises(InvalidCursorError):
        decode_cursor(cursor, BY_NAME, "desc")


def test_cursor_with_invalid_value_for_its_column_is_rejected():
    for spec, value in ((BY_DATE, "ayer"), (BY_CREATED, "2024-01-01T00:00:00")):
        cursor = encode_cursor(spec, "asc", value, uuid4())
        with pytest.raises(InvalidCursorError):
            decode_cursor(cursor, spec, "asc")


def test_contains_pattern_escapes_wildcards():
    assert contains_pattern("ana") == "%ana%"
    assert contains_pattern("100%_x") == "%100\\%\\_x%"
    assert contains_pattern("a\\b") == "%a\\\\b%"


def test_cors_origins_come_from_a_comma_separated_string():
    settings = Settings(
        _env_file=None,
        database_url="postgresql://u:p@h/db",
        jwt_secret="s" * 32,
        admin_email="a@b.com",
        admin_password="p" * 12,
        cors_origins="http://localhost:5173, https://front.example.com/ ,",
    )

    assert settings.cors_origins == ["http://localhost:5173", "https://front.example.com"]
