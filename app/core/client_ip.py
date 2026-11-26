"""IP del cliente detrás de un proxy, sin fiarse de lo que escribe el propio cliente.

Cuando hay un proxy delante (Railway), la conexión TCP llega desde el proxy y la IP real viaja
en el header X-Forwarded-For. Cada proxy de confianza AÑADE AL FINAL la IP de quien se le
conectó:

    X-Forwarded-For: <lo que escribió el cliente>, <IP real, añadida por el proxy>

Todo lo que está a la izquierda lo controla el cliente: puede enviar un
`X-Forwarded-For: 1.2.3.4` falso y el proxy solo añadirá su IP real al final. Por eso se lee
contando desde la DERECHA, tantas posiciones como proxies de confianza haya.
"""

import ipaddress

from starlette.requests import Request

# Un cliente IPv6 suele tener un bloque /64 entero (2^64 direcciones). Si cada dirección fuera
# una clave distinta, rotar la dirección saltaría el límite de intentos.
_IPV6_PREFIX = 64


def _normalize(value: str) -> str | None:
    """La IP como clave de límite, o None si no es una IP válida."""
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        return None
    if address.version == 6:
        return str(ipaddress.ip_network(f"{address}/{_IPV6_PREFIX}", strict=False))
    return str(address)


def client_ip(request: Request, trusted_hops: int) -> str:
    """La IP del cliente. trusted_hops es el número de proxies de confianza delante de la app.

    Con 0 (por defecto) se ignora X-Forwarded-For y se usa la IP de la conexión: es lo correcto
    si la app recibe tráfico directo. Ante cualquier duda (header ausente, más corto de lo
    esperado o con basura) se usa la IP de la conexión.
    """
    peer = request.client.host if request.client else "unknown"
    peer_key = _normalize(peer) or peer
    if trusted_hops <= 0:
        return peer_key

    # Los elementos vacíos NO se descartan: la posición se cuenta desde la derecha y cada
    # elemento corresponde a un salto real; quitarlos desplazaría la cuenta.
    forwarded = [
        item.strip()
        for header in request.headers.getlist("x-forwarded-for")
        for item in header.split(",")
    ]
    if len(forwarded) < trusted_hops:
        return peer_key
    return _normalize(forwarded[-trusted_hops]) or peer_key
