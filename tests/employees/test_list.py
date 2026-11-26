"""GET /employees: paginación por cursor, búsqueda, filtros y orden."""

from uuid import uuid4

import pytest

from app.core import pagination


@pytest.fixture(autouse=True)
def small_pages(monkeypatch):
    # Con páginas de 3 filas, pocos empleados bastan para probar el cursor.
    monkeypatch.setattr(pagination, "PAGE_SIZE", 3)


async def pages(client, **params):
    """Devuelve la lista de páginas de un listado, siguiendo next_cursor."""
    result, after = [], None
    while True:
        query = params | ({"after": after} if after else {})
        response = await client.get("/employees", params=query)
        assert response.status_code == 200, response.text
        body = response.json()
        assert set(body) == {"items", "next_cursor"}
        result.append(body)
        after = body["next_cursor"]
        if after is None:
            return result


def ids(page_list):
    return [e["id"] for page in page_list for e in page["items"]]


async def test_paginates_without_repeating_or_skipping(client, create_employee):
    created = [await create_employee() for _ in range(7)]

    result = await pages(client)

    assert [len(p["items"]) for p in result] == [3, 3, 1]
    assert [p["next_cursor"] is None for p in result] == [False, False, True]
    assert sorted(ids(result)) == sorted(e["id"] for e in created)


async def test_exact_multiple_of_page_size_has_no_empty_last_page(client, create_employee):
    for _ in range(6):
        await create_employee()

    result = await pages(client)

    assert [len(p["items"]) for p in result] == [3, 3]


async def test_empty_listing(client):
    assert (await client.get("/employees")).json() == {"items": [], "next_cursor": None}


async def test_default_order_is_last_name_asc(client, create_employee):
    for last_name in ("Zeta", "Alfa", "Mike", "Bravo"):
        await create_employee(last_name=last_name)

    result = await pages(client)

    names = [e["last_name"] for p in result for e in p["items"]]
    assert names == ["Alfa", "Bravo", "Mike", "Zeta"]


@pytest.mark.parametrize("order", ["asc", "desc"])
async def test_ties_are_broken_by_id_and_stay_stable_across_pages(client, create_employee, order):
    # Todos con la misma fecha: solo el id desempata, y ninguna fila se pierde ni se repite.
    created = [await create_employee(hire_date="2021-06-01") for _ in range(8)]

    result = await pages(client, sort="hire_date", order=order)

    expected = sorted((e["id"] for e in created), reverse=order == "desc")
    assert ids(result) == expected


@pytest.mark.parametrize("order", ["asc", "desc"])
async def test_sort_by_hire_date_with_cursor(client, create_employee, order):
    dates = ["2019-03-01", "2020-01-15", "2020-01-15", "2018-07-20", "2022-02-02", "2021-12-31"]
    for hire_date in dates:
        await create_employee(hire_date=hire_date)

    result = await pages(client, sort="hire_date", order=order)

    found = [e["hire_date"] for p in result for e in p["items"]]
    assert found == sorted(dates, reverse=order == "desc")


async def test_sort_by_created_at_follows_creation_order(client, create_employee):
    created = [await create_employee() for _ in range(5)]

    ascending = ids(await pages(client, sort="created_at"))
    descending = ids(await pages(client, sort="created_at", order="desc"))

    assert ascending == [e["id"] for e in created]
    assert descending == [e["id"] for e in reversed(created)]


async def test_sort_by_first_name(client, create_employee):
    for first_name in ("Delta", "Alfa", "Charlie", "Bravo"):
        await create_employee(first_name=first_name)

    result = await pages(client, sort="first_name", order="desc")

    names = [e["first_name"] for p in result for e in p["items"]]
    assert names == ["Delta", "Charlie", "Bravo", "Alfa"]


async def test_rows_created_between_pages_do_not_shift_the_cursor(client, create_employee):
    for last_name in ("B1", "B2", "B3", "B4", "B5"):
        await create_employee(last_name=last_name)
    first = (await client.get("/employees")).json()

    # Con OFFSET, esta fila nueva desplazaría la segunda página y repetiría una fila.
    await create_employee(last_name="A0")
    second = (await client.get("/employees", params={"after": first["next_cursor"]})).json()

    assert [e["last_name"] for e in second["items"]] == ["B4", "B5"]


async def test_search_is_partial_and_case_insensitive(client, create_employee):
    await create_employee(first_name="Mariana", last_name="Lopez", email="a1@corp.com")
    await create_employee(first_name="Luis", last_name="ANAYA", email="l2@corp.com")
    await create_employee(first_name="Pedro", last_name="Ruiz", email="anabel@corp.com")
    await create_employee(first_name="Otro", last_name="Ruiz", email="z9@corp.com")

    by_name_and_email = await pages(client, q="aNa")
    by_domain = await pages(client, q="CORP.com")

    # Mariana (nombre), ANAYA (apellido) y anabel@ (email); "Otro Ruiz" no coincide.
    assert len(ids(by_name_and_email)) == 3
    assert len(ids(by_domain)) == 4


async def test_search_treats_wildcards_as_plain_text(client, create_employee):
    await create_employee(last_name="Perez")
    await create_employee(last_name="100%_real")

    percent = (await client.get("/employees", params={"q": "%"})).json()["items"]
    underscore = (await client.get("/employees", params={"q": "_"})).json()["items"]

    assert [e["last_name"] for e in percent] == ["100%_real"]
    assert [e["last_name"] for e in underscore] == ["100%_real"]


async def test_search_combines_with_cursor(client, create_employee):
    for i in range(5):
        await create_employee(last_name=f"Match{i}")
    await create_employee(last_name="Other")

    result = await pages(client, q="match")

    assert [len(p["items"]) for p in result] == [3, 2]


async def test_email_filter_is_still_exact(client, create_employee):
    await create_employee(email="ana@example.com")
    await create_employee(email="ana@example.com.mx")

    exact = (await client.get("/employees", params={"email": "ANA@example.com"})).json()["items"]

    assert [e["email"] for e in exact] == ["ana@example.com"]


async def test_filter_by_department_and_manager(client, create_employee):
    boss = await create_employee()
    department = (await client.post("/departments", json={"name": "IT"})).json()
    in_it = await create_employee(department_id=department["id"], manager_id=boss["id"])
    await create_employee(manager_id=boss["id"])
    await create_employee()

    by_department = (
        await client.get("/employees", params={"department_id": department["id"]})
    ).json()["items"]
    by_manager = (await client.get("/employees", params={"manager_id": boss["id"]})).json()
    both = (
        await client.get(
            "/employees", params={"manager_id": boss["id"], "department_id": department["id"]}
        )
    ).json()["items"]

    assert [e["id"] for e in by_department] == [in_it["id"]]
    assert len(by_manager["items"]) == 2
    assert [e["id"] for e in both] == [in_it["id"]]


async def test_has_manager_false_returns_the_roots(client, create_employee):
    root = await create_employee()
    await create_employee(manager_id=root["id"])
    await create_employee(manager_id=root["id"])

    roots = (await client.get("/employees", params={"has_manager": False})).json()["items"]
    managed = (await client.get("/employees", params={"has_manager": True})).json()["items"]

    assert [e["id"] for e in roots] == [root["id"]]
    assert len(managed) == 2


async def test_filter_by_current_job_title(
    client, create_employee, create_job_title, assign_position
):
    dev = await create_job_title("Developer")
    qa = await create_job_title("QA")
    ana = await create_employee()
    luis = await create_employee()
    await create_employee()
    await assign_position(ana["id"], dev["id"], "2020-01-01")
    # Luis fue Developer, pero su puesto ACTUAL es QA.
    await assign_position(luis["id"], dev["id"], "2019-01-01")
    await assign_position(luis["id"], qa["id"], "2021-01-01")

    developers = (await client.get("/employees", params={"job_title_id": dev["id"]})).json()
    testers = (await client.get("/employees", params={"job_title_id": qa["id"]})).json()

    assert [e["id"] for e in developers["items"]] == [ana["id"]]
    assert [e["id"] for e in testers["items"]] == [luis["id"]]


async def test_is_active_omitted_returns_all_and_explicit_value_filters(client, create_employee):
    active = await create_employee()
    gone = await create_employee()
    await client.delete(f"/employees/{gone['id']}")

    everyone = (await client.get("/employees")).json()["items"]
    only_active = (await client.get("/employees", params={"is_active": True})).json()["items"]
    only_inactive = (await client.get("/employees", params={"is_active": False})).json()["items"]

    assert {e["id"] for e in everyone} == {active["id"], gone["id"]}
    assert [e["id"] for e in only_active] == [active["id"]]
    assert [e["id"] for e in only_inactive] == [gone["id"]]


@pytest.mark.parametrize(
    "params",
    [
        {"sort": "salary"},
        {"sort": "id"},
        {"order": "up"},
        {"after": "no-es-un-cursor"},
        {"after": ""},
        {"q": ""},
        {"q": "   "},
        {"department_id": "no-uuid"},
        {"has_manager": "tal-vez"},
    ],
)
async def test_invalid_query_is_422(client, params):
    response = await client.get("/employees", params=params)

    assert response.status_code == 422
    assert response.json()["error"] == "validation_error"


async def test_cursor_from_another_sort_is_422(client, create_employee):
    for _ in range(5):
        await create_employee()
    cursor = (await client.get("/employees")).json()["next_cursor"]

    response = await client.get("/employees", params={"after": cursor, "sort": "hire_date"})

    assert (response.status_code, response.json()["error"]) == (422, "validation_error")


async def test_limit_and_offset_are_ignored(client, create_employee):
    for _ in range(5):
        await create_employee()

    page = (await client.get("/employees", params={"limit": 1, "offset": 4})).json()

    assert len(page["items"]) == 3  # el servidor fija el tamaño de página


async def test_unknown_department_filter_returns_empty(client, create_employee):
    await create_employee()

    page = (await client.get("/employees", params={"department_id": str(uuid4())})).json()

    assert page == {"items": [], "next_cursor": None}
