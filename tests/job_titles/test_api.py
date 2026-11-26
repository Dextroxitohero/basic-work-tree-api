from uuid import uuid4


async def test_crud(client, create_job_title):
    title = await create_job_title("Developer")
    url = f"/job-titles/{title['id']}"

    updated = await client.patch(url, json={"description": "Escribe código", "is_active": False})

    assert updated.status_code == 200
    assert (await client.get(url)).json() == updated.json()
    assert updated.json()["description"] == "Escribe código"
    active = (await client.get("/job-titles", params={"is_active": True})).json()
    assert active == []
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


async def test_search_filter_and_order(client, create_job_title):
    await create_job_title("Backend Developer")
    await create_job_title("Frontend Developer")
    designer = await create_job_title("Designer")
    await client.patch(f"/job-titles/{designer['id']}", json={"is_active": False})

    everything = (await client.get("/job-titles")).json()
    developers = (await client.get("/job-titles", params={"q": "DEVELOPER"})).json()
    descending = (await client.get("/job-titles", params={"order": "desc"})).json()
    active_designers = (
        await client.get("/job-titles", params={"q": "design", "is_active": True})
    ).json()

    assert len(everything) == 3  # sin is_active: activos e inactivos
    assert [t["name"] for t in developers] == ["Backend Developer", "Frontend Developer"]
    assert [t["name"] for t in descending] == [
        "Frontend Developer",
        "Designer",
        "Backend Developer",
    ]
    assert active_designers == []


async def test_invalid_query_is_422(client):
    for params in ({"sort": "created_at"}, {"order": "x"}, {"q": ""}):
        response = await client.get("/job-titles", params=params)

        assert (response.status_code, response.json()["error"]) == (422, "validation_error")
