"""GET /departments: paginación por cursor, búsqueda y orden."""

import pytest

from app.core import pagination


@pytest.fixture(autouse=True)
def small_pages(monkeypatch):
    monkeypatch.setattr(pagination, "PAGE_SIZE", 3)


async def create_departments(client, *names):
    return [(await client.post("/departments", json={"name": name})).json() for name in names]


async def test_paginates_by_name_by_default(client, get_all):
    await create_departments(client, "Ventas", "Legal", "Finanzas", "TI", "Compras", "RRHH", "Ops")

    first = (await client.get("/departments")).json()
    everything = await get_all("/departments")

    assert len(first["items"]) == 3
    assert first["next_cursor"] is not None
    names = [d["name"] for d in everything]
    assert len(names) == 7
    assert names == sorted(names)


@pytest.mark.parametrize("order", ["asc", "desc"])
async def test_sort_by_name_with_cursor(client, get_all, order):
    await create_departments(client, "D", "B", "F", "A", "E", "C", "G")

    found = await get_all("/departments", sort="name", order=order)

    names = [d["name"] for d in found]
    assert names == sorted(names, reverse=order == "desc")


@pytest.mark.parametrize("order", ["asc", "desc"])
async def test_sort_by_created_at_with_cursor(client, get_all, order):
    created = await create_departments(client, "D", "B", "F", "A", "E", "C", "G")

    found = await get_all("/departments", sort="created_at", order=order)

    created_ids = [d["id"] for d in created]
    expected = created_ids if order == "asc" else created_ids[::-1]
    assert [d["id"] for d in found] == expected


async def test_search_by_name_is_partial_and_case_insensitive(client):
    await create_departments(
        client, "Recursos Humanos", "Tecnología", "Recursos Técnicos", "Ventas"
    )

    found = (await client.get("/departments", params={"q": "RECURSOS"})).json()["items"]

    assert [d["name"] for d in found] == ["Recursos Humanos", "Recursos Técnicos"]


async def test_employee_count_in_every_listed_department(client, create_employee):
    it, _ = await create_departments(client, "IT", "HR")
    for _ in range(2):
        await create_employee(department_id=it["id"])

    listed = (await client.get("/departments")).json()["items"]

    assert {d["name"]: d["employee_count"] for d in listed} == {"IT": 2, "HR": 0}


@pytest.mark.parametrize(
    "params",
    [{"sort": "manager_id"}, {"order": "x"}, {"after": "basura"}, {"q": ""}],
)
async def test_invalid_query_is_422(client, params):
    response = await client.get("/departments", params=params)

    assert (response.status_code, response.json()["error"]) == (422, "validation_error")


async def test_cursor_from_another_order_is_422(client):
    await create_departments(client, "A", "B", "C", "D")
    cursor = (await client.get("/departments")).json()["next_cursor"]

    response = await client.get("/departments", params={"after": cursor, "order": "desc"})

    assert (response.status_code, response.json()["error"]) == (422, "validation_error")
