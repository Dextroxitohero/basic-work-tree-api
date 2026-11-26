ALLOWED = "http://localhost:5173"  # definido en conftest.py


async def preflight(client, origin, method="PATCH"):
    return await client.options(
        "/employees",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": method,
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )


async def test_preflight_from_allowed_origin(anonymous_client):
    response = await preflight(anonymous_client, ALLOWED)

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == ALLOWED
    assert "PATCH" in response.headers["access-control-allow-methods"]
    allowed_headers = response.headers["access-control-allow-headers"].lower()
    assert "authorization" in allowed_headers
    assert "content-type" in allowed_headers


async def test_preflight_from_unknown_origin_is_rejected(anonymous_client):
    response = await preflight(anonymous_client, "https://malicioso.example.com")

    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


async def test_preflight_with_unsupported_method_is_rejected(anonymous_client):
    response = await preflight(anonymous_client, ALLOWED, method="PUT")

    assert response.status_code == 400


async def test_simple_request_from_allowed_origin_gets_the_header(client):
    response = await client.get("/employees", headers={"Origin": ALLOWED})

    assert response.headers["access-control-allow-origin"] == ALLOWED
