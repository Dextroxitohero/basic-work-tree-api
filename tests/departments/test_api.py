from uuid import uuid4


async def test_detail_has_employee_count_of_active_employees_only(client, create_employee):
    boss = await create_employee()
    department = (
        await client.post("/departments", json={"name": "IT", "manager_id": boss["id"]})
    ).json()
    await create_employee(department_id=department["id"])
    inactive = await create_employee(department_id=department["id"])
    await client.delete(f"/employees/{inactive['id']}")

    detail = (await client.get(f"/departments/{department['id']}")).json()
    listed = (await client.get("/departments")).json()["items"]

    assert department["employee_count"] == 0  # la respuesta del POST también lo incluye
    assert detail["manager_id"] == boss["id"]
    assert detail["employee_count"] == 1
    assert "employees" not in detail
    assert listed == [detail]


async def test_update_and_list(client):
    department = (await client.post("/departments", json={"name": "IT"})).json()

    renamed = await client.patch(f"/departments/{department['id']}", json={"name": "Tech"})

    assert renamed.status_code == 200
    assert renamed.json()["employee_count"] == 0
    listed = (await client.get("/departments")).json()["items"]
    assert [d["name"] for d in listed] == ["Tech"]


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
