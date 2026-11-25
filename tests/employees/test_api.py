import asyncio
from datetime import date, timedelta
from uuid import uuid4

import pytest


async def test_create_returns_the_contract(client):
    response = await client.post(
        "/employees",
        json={
            "first_name": "  Ana ",
            "last_name": "López",
            "email": "Ana.Lopez@Example.com",
            "hire_date": "2020-01-01",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["first_name"] == "Ana"
    assert body["email"] == "ana.lopez@example.com"
    assert body["is_active"] is True
    assert body["current_position"] is None


@pytest.mark.parametrize(
    "override",
    [
        {"email": "no-es-un-email"},
        {"first_name": "   "},
        {"first_name": "x" * 81},
        {"hire_date": (date.today() + timedelta(days=1)).isoformat()},
        {"campo_desconocido": 1},
    ],
)
async def test_create_rejects_invalid_body(client, override):
    body = {
        "first_name": "A",
        "last_name": "B",
        "email": "a@example.com",
        "hire_date": "2020-01-01",
    }

    response = await client.post("/employees", json=body | override)

    assert response.status_code == 422
    assert response.json()["error"] == "validation_error"


async def test_retrying_create_conflicts_and_resource_can_be_recovered(client, create_employee):
    employee = await create_employee(email="ana@example.com")

    retry = await client.post(
        "/employees",
        json={
            "first_name": "Ana",
            "last_name": "X",
            "email": "ANA@example.com",
            "hire_date": "2020-01-01",
        },
    )
    found = await client.get("/employees", params={"email": "ANA@example.com"})

    assert retry.status_code == 409
    assert retry.json()["error"] == "email_already_exists"
    assert [e["id"] for e in found.json()] == [employee["id"]]


async def test_unknown_employee_is_404(client):
    for path in ("", "/reports", "/tree", "/positions", "/positions/current"):
        response = await client.get(f"/employees/{uuid4()}{path}")
        assert response.status_code == 404
        assert response.json()["error"] == "employee_not_found"


async def test_create_with_unknown_references(client):
    body = {
        "first_name": "A",
        "last_name": "B",
        "email": "a@example.com",
        "hire_date": "2020-01-01",
    }

    manager = await client.post("/employees", json=body | {"manager_id": str(uuid4())})
    department = await client.post("/employees", json=body | {"department_id": str(uuid4())})

    assert (manager.status_code, manager.json()["error"]) == (404, "employee_not_found")
    assert (department.status_code, department.json()["error"]) == (404, "department_not_found")


async def test_patch_distinguishes_omitted_from_null(client, create_employee):
    boss = await create_employee()
    employee = await create_employee(manager_id=boss["id"], phone="123")
    url = f"/employees/{employee['id']}"

    omitted = await client.patch(url, json={"first_name": "Eva"})
    cleared = await client.patch(url, json={"manager_id": None})
    invalid = await client.patch(url, json={"first_name": None})

    assert omitted.json()["manager_id"] == boss["id"]
    assert omitted.json()["phone"] == "123"
    assert cleared.json()["manager_id"] is None
    assert cleared.json()["first_name"] == "Eva"
    assert invalid.status_code == 422


async def test_repeating_patch_is_idempotent(client, create_employee):
    employee = await create_employee()
    url = f"/employees/{employee['id']}"

    first = await client.patch(url, json={"phone": "555"})
    second = await client.patch(url, json={"phone": "555"})

    assert first.json()["updated_at"] > employee["updated_at"]
    assert second.json() == first.json()


async def test_manager_cycles_are_rejected(client, create_employee):
    a = await create_employee()
    b = await create_employee(manager_id=a["id"])
    c = await create_employee(manager_id=b["id"])

    for manager in (a, b, c):
        response = await client.patch(f"/employees/{a['id']}", json={"manager_id": manager["id"]})
        assert response.status_code == 409
        assert response.json()["error"] == "circular_manager_reference"


async def test_concurrent_requests_cannot_create_a_cycle(client, create_employee):
    for _ in range(5):
        a, b = await create_employee(), await create_employee()

        responses = await asyncio.gather(
            client.patch(f"/employees/{a['id']}", json={"manager_id": b["id"]}),
            client.patch(f"/employees/{b['id']}", json={"manager_id": a["id"]}),
        )

        assert sorted(r.status_code for r in responses) == [200, 409]


async def test_inactive_manager_is_rejected(client, create_employee):
    boss = await create_employee()
    employee = await create_employee()
    await client.delete(f"/employees/{boss['id']}")

    response = await client.patch(f"/employees/{employee['id']}", json={"manager_id": boss["id"]})

    assert (response.status_code, response.json()["error"]) == (409, "inactive_manager")


async def test_detail_reports_and_tree(client, create_employee, create_job_title, assign_position):
    ceo = await create_employee(last_name="CEO")
    lead = await create_employee(last_name="Lead", manager_id=ceo["id"])
    dev = await create_employee(last_name="Dev", manager_id=lead["id"])
    title = await create_job_title()
    await assign_position(lead["id"], title["id"], "2021-01-01")

    detail = (await client.get(f"/employees/{ceo['id']}")).json()
    reports = (await client.get(f"/employees/{ceo['id']}/reports")).json()
    tree = (await client.get(f"/employees/{ceo['id']}/tree")).json()
    subtree = (await client.get(f"/employees/{lead['id']}/tree")).json()

    assert [e["id"] for e in detail["direct_reports"]] == [lead["id"]]
    assert detail["direct_reports"][0]["current_position"]["job_title"]["name"] == "Developer"
    assert [e["id"] for e in reports] == [lead["id"]]
    assert tree["employee"]["id"] == ceo["id"]
    assert tree["reports"][0]["employee"]["id"] == lead["id"]
    assert tree["reports"][0]["reports"][0]["employee"]["id"] == dev["id"]
    assert subtree["employee"]["id"] == lead["id"]
    assert len(subtree["reports"]) == 1


@pytest.mark.parametrize("via_patch", [False, True])
async def test_deactivation_releases_responsibilities(
    client, create_employee, create_job_title, assign_position, via_patch
):
    boss = await create_employee()
    report = await create_employee(manager_id=boss["id"])
    title = await create_job_title()
    await assign_position(boss["id"], title["id"], "2021-01-01")
    department = (
        await client.post("/departments", json={"name": "IT", "manager_id": boss["id"]})
    ).json()
    url = f"/employees/{boss['id']}"

    if via_patch:
        response = await client.patch(url, json={"is_active": False})
        assert response.status_code == 200
        assert response.json()["current_position"] is None
    else:
        assert (await client.delete(url)).status_code == 204
        # Idempotente: repetir la baja no es un error.
        assert (await client.delete(url)).status_code == 204

    detail = (await client.get(url)).json()
    assert detail["is_active"] is False
    assert detail["position_history"][0]["end_date"] == date.today().isoformat()
    assert (await client.get(f"/employees/{report['id']}")).json()["manager_id"] is None
    assert (await client.get(f"/departments/{department['id']}")).json()["manager_id"] is None
    active_ids = [e["id"] for e in (await client.get("/employees")).json()]
    inactive = (await client.get("/employees", params={"is_active": False})).json()
    assert boss["id"] not in active_ids
    assert [e["id"] for e in inactive] == [boss["id"]]


async def test_reactivation(client, create_employee):
    employee = await create_employee()
    await client.delete(f"/employees/{employee['id']}")

    response = await client.patch(f"/employees/{employee['id']}", json={"is_active": True})

    assert response.json()["is_active"] is True
