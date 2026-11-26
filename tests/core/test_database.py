"""Los errores de la base de datos no deben filtrar los valores de las consultas."""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.database import engine

SECRET = "valor-secreto-que-no-debe-salir-en-logs"
# Falla con "division by zero" y lleva el valor secreto como parámetro de la consulta.
FAILING = text("select 1 / (select 0) where cast(:value as text) = cast(:value as text)")


async def test_query_parameters_are_hidden_in_database_errors():
    with pytest.raises(DBAPIError) as error:
        async with engine.connect() as connection:
            await connection.execute(FAILING, {"value": SECRET})

    assert "division by zero" in str(error.value)
    assert SECRET not in str(error.value)
    assert SECRET not in repr(error.value)
    assert "[parameters" not in str(error.value)


async def test_control_without_the_option_the_value_does_appear():
    # Sin hide_parameters el mismo error sí contiene el valor: así el test anterior es válido.
    plain = create_async_engine(engine.url)
    try:
        with pytest.raises(DBAPIError) as error:
            async with plain.connect() as connection:
                await connection.execute(FAILING, {"value": SECRET})
    finally:
        await plain.dispose()

    assert SECRET in str(error.value)
