from app.core.database import AsyncSessionLocal
from app.seed.data import DEPARTMENTS
from app.seed.loader import seed


async def run_seed() -> int:
    async with AsyncSessionLocal.begin() as session:
        return await seed(session)


def count_nodes(node: dict) -> int:
    return 1 + sum(count_nodes(child) for child in node["reports"])


async def test_seed_creates_20_employees_with_different_positions(client):
    assert await run_seed() == 20

    employees = (await client.get("/employees")).json()
    titles = {e["current_position"]["job_title"]["name"] for e in employees}
    roots = [e for e in employees if e["manager_id"] is None]
    tree = (await client.get(f"/employees/{roots[0]['id']}/tree")).json()
    departments = (await client.get("/departments")).json()

    assert len(employees) == 20
    assert len(titles) == 20
    assert len(roots) == 1
    assert count_nodes(tree) == 20
    assert {d["name"] for d in departments} == DEPARTMENTS.keys()
    assert all(d["manager_id"] for d in departments)


async def test_seed_history_is_consistent(client):
    await run_seed()
    employee = (
        await client.get("/employees", params={"email": "andres.molina@example.com"})
    ).json()

    history = (await client.get(f"/employees/{employee[0]['id']}/positions")).json()

    assert [(p["start_date"], p["end_date"]) for p in history] == [
        ("2020-01-01", None),
        ("2016-04-01", "2019-12-31"),
        ("2013-01-14", "2016-03-31"),
    ]
    assert employee[0]["hire_date"] == "2013-01-14"


async def test_seed_is_idempotent_and_keeps_changes(client):
    await run_seed()
    employee = (await client.get("/employees", params={"email": "ivan.romero@example.com"})).json()[
        0
    ]
    await client.patch(f"/employees/{employee['id']}", json={"phone": "555"})
    await client.delete(f"/employees/{employee['id']}")

    assert await run_seed() == 0

    after = (await client.get(f"/employees/{employee['id']}")).json()
    assert (after["phone"], after["is_active"]) == ("555", False)
    assert len((await client.get("/employees")).json()) == 19
