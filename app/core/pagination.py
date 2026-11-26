"""Paginación por cursor (keyset).

Con OFFSET, la base de datos recorre y descarta todas las filas anteriores, y si alguien
inserta o borra mientras se pagina, el cliente ve filas repetidas o se salta alguna. El cursor
recuerda la ÚLTIMA fila entregada y la siguiente página empieza justo después:

    WHERE (columna_de_orden, id) > (valor_del_cursor, id_del_cursor)
    ORDER BY columna_de_orden, id
    LIMIT 51          -- una de más: si llega, hay página siguiente

El id desempata las filas con el mismo valor de orden, así el orden es total y estable. Por
eso el cursor guarda el par (valor, id) y no solo el id: con UUID v4 ordenar por id no da
orden cronológico, pero con el par compuesto no hace falta.
"""

import base64
import binascii
import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import Select, asc, desc, literal, tuple_
from sqlalchemy.orm import InstrumentedAttribute

from app.core.exceptions import InvalidInputError

# El tamaño de página lo fija el servidor, no el cliente.
PAGE_SIZE = 50

Order = Literal["asc", "desc"]


class InvalidCursorError(InvalidInputError):
    code = "validation_error"
    message = "El cursor 'after' no es válido"


@dataclass
class Page[T]:
    """Una página de resultados. next_cursor es None en la última."""

    items: list[T]
    next_cursor: str | None


def parse_text(value: str) -> str:
    if "\x00" in value:  # PostgreSQL no admite el carácter NUL en un texto
        raise ValueError("NUL en el texto")
    return value


def parse_aware_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:  # las columnas son TIMESTAMPTZ: una fecha sin zona es inválida
        raise ValueError("fecha sin zona horaria")
    return parsed


@dataclass(frozen=True)
class SortSpec:
    """Una columna por la que se puede ordenar y cómo leer su valor desde el cursor."""

    name: str  # el valor del parámetro ?sort=
    column: InstrumentedAttribute
    parse: Callable[[str], Any] = parse_text


def _serialize(value: Any) -> str:
    return value.isoformat() if isinstance(value, date | datetime) else str(value)


def encode_cursor(spec: SortSpec, order: Order, value: Any, row_id: UUID) -> str:
    # Se guarda también sort y order: un cursor de un orden no sirve para otro.
    payload = {"s": spec.name, "o": order, "v": _serialize(value), "i": str(row_id)}
    raw = json.dumps(payload, separators=(",", ":")).encode()
    # Opaco para el cliente: base64 sin relleno, seguro para usar en una URL.
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_cursor(cursor: str, spec: SortSpec, order: Order) -> tuple[Any, UUID]:
    try:
        raw = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4))
        payload = json.loads(raw)
        if payload["s"] != spec.name or payload["o"] != order:
            raise ValueError("el cursor es de otro orden")
        if not isinstance(payload["v"], str):
            raise ValueError("valor inválido")
        return spec.parse(payload["v"]), UUID(payload["i"])
    except (ValueError, KeyError, TypeError, binascii.Error) as exc:
        # json.JSONDecodeError y UnicodeDecodeError son ValueError.
        raise InvalidCursorError(details=[{"loc": ["query", "after"]}]) from exc


def apply_page(
    stmt: Select,
    *,
    spec: SortSpec,
    id_column: InstrumentedAttribute,
    order: Order,
    after: str | None,
) -> Select:
    """Agrega al query el orden, el punto de partida del cursor y el límite."""
    column = spec.column
    if after is not None:
        value, row_id = decode_cursor(after, spec, order)
        # Comparación de filas de PostgreSQL: (a, b) > (x, y) usa el mismo orden que ORDER BY.
        position = tuple_(column, id_column)
        marker = tuple_(literal(value, column.type), literal(row_id, id_column.type))
        stmt = stmt.where(position > marker if order == "asc" else position < marker)
    direction = asc if order == "asc" else desc
    # Pide una fila de más solo para saber si hay otra página.
    return stmt.order_by(direction(column), direction(id_column)).limit(PAGE_SIZE + 1)


def build_page[T](rows: Sequence[T], *, spec: SortSpec, order: Order) -> Page[T]:
    """Recorta la fila extra y calcula el cursor de la página siguiente."""
    items = list(rows[:PAGE_SIZE])
    next_cursor = None
    if len(rows) > PAGE_SIZE:
        last = items[-1]
        next_cursor = encode_cursor(spec, order, getattr(last, spec.column.key), last.id)
    return Page(items=items, next_cursor=next_cursor)


def contains_pattern(term: str) -> str:
    """Patrón para ILIKE '%term%'. Escapa % y _ para que se busquen como texto literal."""
    escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"
