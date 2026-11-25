from uuid import uuid4


async def test_crud(client, create_job_title):
    title = await create_job_title("Developer")
    url = f"/job-titles/{title['id']}"

    updated = await client.patch(url, json={"description": "Escribe código", "is_active": False})

    assert updated.status_code == 200
    assert (await client.get(url)).json() == updated.json()
    assert updated.json()["description"] == "Escribe código"
    assert (await client.get("/job-titles")).json() == []
    inactive = (await client.get("/job-titles", params={"is_active": False})).json()
    assert [t["id"] for t in inactive] == [title["id"]]


async def test_duplicated_name(client, create_job_title):
    await create_job_title("Developer")
    other = await create_job_title("Designer")

    created = await client.post("/job-titles", json={"name": "Developer"})
    renamed = await client.patch(f"/job-titles/{other['id']}", json={"name": "Developer"})

    for response in (created, renamed):
        assert (response.status_code, response.json()["error"]) == (409, "job_title_name_exists")


async def test_not_found(client):
    response = await client.get(f"/job-titles/{uuid4()}")

    assert (response.status_code, response.json()["error"]) == (404, "job_title_not_found")
