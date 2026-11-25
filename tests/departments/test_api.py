from uuid import uuid4


async def test_detail_lists_only_active_employees(client, create_employee):
    boss = await create_employee()
    department = (
        await client.post("/departments", json={"name": "IT", "manager_id": boss["id"]})
    ).json()
    active = await create_employee(department_id=department["id"])
    inactive = await create_employee(department_id=department["id"])
    await client.delete(f"/employees/{inactive['id']}")

    detail = (await client.get(f"/departments/{department['id']}")).json()

    assert detail["manager_id"] == boss["id"]
    assert [e["id"] for e in detail["employees"]] == [active["id"]]


async def test_update_and_list(client):
    department = (await client.post("/departments", json={"name": "IT"})).json()

    renamed = await client.patch(f"/departments/{department['id']}", json={"name": "Tech"})

    assert renamed.status_code == 200
    assert [d["name"] for d in (await client.get("/departments")).json()] == ["Tech"]


async def test_duplicated_name(client):
    await client.post("/departments", json={"name": "IT"})

    response = await client.post("/departments", json={"name": "IT"})

    assert (response.status_code, response.json()["error"]) == (409, "department_name_exists")


async def test_manager_must_exist_and_be_active(client, create_employee):
    employee = await create_employee()
    await client.delete(f"/employees/{employee['id']}")

    unknown = await client.post("/departments", json={"name": "A", "manager_id": str(uuid4())})
    inactive = await client.post("/departments", json={"name": "A", "manager_id": employee["id"]})

    assert (unknown.status_code, unknown.json()["error"]) == (404, "employee_not_found")
    assert (inactive.status_code, inactive.json()["error"]) == (409, "inactive_manager")


async def test_not_found(client):
    read = await client.get(f"/departments/{uuid4()}")
    write = await client.patch(f"/departments/{uuid4()}", json={"name": "X"})

    for response in (read, write):
        assert (response.status_code, response.json()["error"]) == (404, "department_not_found")
