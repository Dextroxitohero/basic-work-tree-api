import asyncio
from datetime import date, timedelta
from uuid import uuid4

import pytest


async def test_new_position_closes_the_previous_one(
    client, create_employee, create_job_title, assign_position
):
    employee = await create_employee()
    junior = await create_job_title("Junior")
    senior = await create_job_title("Senior")

    await assign_position(employee["id"], junior["id"], "2021-01-01")
    await assign_position(employee["id"], senior["id"], "2023-06-15")

    history = (await client.get(f"/employees/{employee['id']}/positions")).json()
    current = (await client.get(f"/employees/{employee['id']}/positions/current")).json()
    assert [(p["job_title"]["name"], p["start_date"], p["end_date"]) for p in history] == [
        ("Senior", "2023-06-15", None),
        ("Junior", "2021-01-01", "2023-06-14"),
    ]
    assert current["job_title"]["name"] == "Senior"
    assert current["salary"] == "1500.50"


@pytest.mark.parametrize("start_date", ["2021-01-01", "2020-12-31"])
async def test_overlapping_position(
    client, create_employee, create_job_title, assign_position, start_date
):
    employee = await create_employee()
    title = await create_job_title()
    await assign_position(employee["id"], title["id"], "2021-01-01")

    response = await client.post(
        f"/employees/{employee['id']}/positions",
        json={"job_title_id": title["id"], "salary": 10, "start_date": start_date},
    )

    assert (response.status_code, response.json()["error"]) == (409, "overlapping_position")
    history = (await client.get(f"/employees/{employee['id']}/positions")).json()
    assert len(history) == 1
    assert history[0]["end_date"] is None


async def test_position_cannot_overlap_a_closed_one(
    client, create_employee, create_job_title, assign_position
):
    employee = await create_employee()
    title = await create_job_title()
    await assign_position(employee["id"], title["id"], "2021-01-01")
    await client.delete(f"/employees/{employee['id']}")
    await client.patch(f"/employees/{employee['id']}", json={"is_active": True})

    response = await client.post(
        f"/employees/{employee['id']}/positions",
        json={"job_title_id": title["id"], "salary": 10, "start_date": "2022-01-01"},
    )

    assert (response.status_code, response.json()["error"]) == (409, "overlapping_position")


async def test_concurrent_assignments_create_only_one(client, create_employee, create_job_title):
    employee = await create_employee()
    title = await create_job_title()
    body = {"job_title_id": title["id"], "salary": 10, "start_date": "2021-01-01"}

    responses = await asyncio.gather(
        *(client.post(f"/employees/{employee['id']}/positions", json=body) for _ in range(5))
    )

    assert sorted(r.status_code for r in responses) == [201, 409, 409, 409, 409]


@pytest.mark.parametrize(
    "override",
    [
        {"salary": 0},
        {"salary": "-1"},
        {"salary": "10.123"},
        {"salary": "99999999999.00"},
        {"salary": "NaN"},
        {"start_date": (date.today() + timedelta(days=1)).isoformat()},
        {"job_title_id": "no-es-uuid"},
    ],
)
async def test_invalid_body(client, create_employee, override):
    employee = await create_employee()
    body = {"job_title_id": str(uuid4()), "salary": 10, "start_date": "2021-01-01"}

    response = await client.post(f"/employees/{employee['id']}/positions", json=body | override)

    assert response.status_code == 422


async def test_assignment_business_errors(client, create_employee, create_job_title):
    employee = await create_employee()
    title = await create_job_title()
    url = f"/employees/{employee['id']}/positions"
    body = {"job_title_id": title["id"], "salary": 10, "start_date": "2021-01-01"}

    no_current = await client.get(f"{url}/current")
    unknown_title = await client.post(url, json=body | {"job_title_id": str(uuid4())})
    await client.patch(f"/job-titles/{title['id']}", json={"is_active": False})
    inactive_title = await client.post(url, json=body)
    await client.delete(f"/employees/{employee['id']}")
    inactive_employee = await client.post(url, json=body)

    assert (no_current.status_code, no_current.json()["error"]) == (404, "no_active_position")
    assert (unknown_title.status_code, unknown_title.json()["error"]) == (
        404,
        "job_title_not_found",
    )
    assert (inactive_title.status_code, inactive_title.json()["error"]) == (
        409,
        "job_title_inactive",
    )
    assert (inactive_employee.status_code, inactive_employee.json()["error"]) == (
        409,
        "employee_inactive",
    )
