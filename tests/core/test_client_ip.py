"""IP del cliente detrás de un proxy: no debe poder falsificarse con X-Forwarded-For."""

import pytest
from starlette.requests import Request

from app.core.client_ip import client_ip

PEER = "10.0.0.1"  # la IP del proxy: la de la conexión TCP


def make_request(*forwarded: str, peer: str | None = PEER) -> Request:
    """Una petición con una línea X-Forwarded-For por cada valor recibido."""
    return Request(
        {
            "type": "http",
            "headers": [(b"x-forwarded-for", value.encode()) for value in forwarded],
            "client": (peer, 40_000) if peer else None,
        }
    )


def test_without_trusted_proxies_the_header_is_ignored():
    assert client_ip(make_request("6.6.6.6"), trusted_hops=0) == PEER
    assert client_ip(make_request("6.6.6.6, 7.7.7.7"), trusted_hops=0) == PEER
    assert client_ip(make_request(), trusted_hops=0) == PEER


def test_with_one_proxy_the_ip_is_the_last_entry():
    assert client_ip(make_request("203.0.113.9"), trusted_hops=1) == "203.0.113.9"


@pytest.mark.parametrize(
    "forged",
    ["6.6.6.6", "6.6.6.6, 7.7.7.7", "1.2.3.4, 5.6.7.8, 9.9.9.9", "127.0.0.1", "::1", "basura"],
)
def test_what_the_client_writes_on_the_left_never_changes_the_result(forged):
    # El proxy de confianza añade la IP real AL FINAL: lo anterior lo escribió el cliente.
    request = make_request(f"{forged}, 203.0.113.9")

    assert client_ip(request, trusted_hops=1) == "203.0.113.9"


def test_with_two_proxies_the_ip_is_the_second_from_the_end():
    request = make_request("6.6.6.6, 203.0.113.9, 10.0.0.5")

    assert client_ip(request, trusted_hops=2) == "203.0.113.9"


def test_several_header_lines_are_read_as_one_list():
    request = make_request("6.6.6.6", "203.0.113.9")

    assert client_ip(request, trusted_hops=1) == "203.0.113.9"


@pytest.mark.parametrize(
    ("forwarded", "hops"),
    [
        ((), 1),  # no hay header
        (("203.0.113.9",), 2),  # más corto de lo esperado
        (("6.6.6.6, no-es-una-ip",), 1),  # la entrada de confianza no es una IP
        (("6.6.6.6, ",), 1),
        (("",), 1),
    ],
)
def test_anything_odd_falls_back_to_the_connection_ip(forwarded, hops):
    assert client_ip(make_request(*forwarded), trusted_hops=hops) == PEER


def test_ipv6_addresses_of_the_same_64_block_share_one_key():
    first = client_ip(make_request("2001:db8:1:2::1"), trusted_hops=1)
    same_block = client_ip(make_request("2001:db8:1:2:ffff:ffff:ffff:ffff"), trusted_hops=1)
    other_block = client_ip(make_request("2001:db8:1:3::1"), trusted_hops=1)

    assert first == same_block == "2001:db8:1:2::/64"
    assert other_block != first


def test_ipv4_is_kept_as_is():
    assert client_ip(make_request("203.0.113.9"), trusted_hops=1) == "203.0.113.9"


def test_no_client_at_all():
    assert client_ip(make_request(peer=None), trusted_hops=0) == "unknown"
    assert client_ip(make_request(peer=None), trusted_hops=1) == "unknown"
