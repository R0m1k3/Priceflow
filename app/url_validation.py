"""URL validation utilities for security."""

import ipaddress
import socket
from urllib.parse import urlparse


class URLValidationError(Exception):
    """Raised when URL validation fails."""

    pass


# Blocked schemes that could be used for SSRF
BLOCKED_SCHEMES = {"file", "javascript", "data", "ftp"}

# Hostnames that must never be reached, whatever they resolve to
BLOCKED_HOSTNAMES = {
    "localhost",
    "metadata",
    "metadata.google.internal",
    "instance-data",
}


def _is_forbidden_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Return True if the address is private, loopback, link-local, reserved, etc."""
    if isinstance(ip, ipaddress.IPv6Address):
        # IPv4-mapped (::ffff:a.b.c.d) / 6to4 / Teredo: check the embedded IPv4 too
        if ip.ipv4_mapped is not None and _is_forbidden_ip(ip.ipv4_mapped):
            return True
        if ip.sixtofour is not None and _is_forbidden_ip(ip.sixtofour):
            return True
        if ip.teredo is not None and any(_is_forbidden_ip(t) for t in ip.teredo):
            return True
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
        or not ip.is_global
    )


def _resolve_host(hostname: str) -> list[str]:
    """Resolve a hostname to the list of its IP addresses."""
    infos = socket.getaddrinfo(hostname, None, proto=socket.IPPROTO_TCP)
    return list({info[4][0] for info in infos})


def validate_url(url: str, allow_private: bool = False) -> None:
    """
    Validate URL for security (SSRF prevention).

    The hostname is resolved and every resulting address must be public
    (no private, loopback, link-local, reserved or cloud metadata ranges,
    IPv4-mapped IPv6 included).

    Args:
        url: URL to validate
        allow_private: Allow private/internal IPs (default: False)

    Raises:
        URLValidationError: If URL is invalid or blocked
    """
    if not url or not isinstance(url, str):
        raise URLValidationError("URL must be a non-empty string")

    try:
        parsed = urlparse(url.strip())
    except Exception as e:
        raise URLValidationError(f"Invalid URL format: {e}") from e

    # Check scheme
    if not parsed.scheme:
        raise URLValidationError("URL must include a scheme (http:// or https://)")

    if parsed.scheme.lower() in BLOCKED_SCHEMES:
        raise URLValidationError(f"Blocked URL scheme: {parsed.scheme}")

    if parsed.scheme.lower() not in {"http", "https"}:
        raise URLValidationError(f"Only HTTP/HTTPS schemes allowed, got: {parsed.scheme}")

    # Check hostname
    if not parsed.hostname:
        raise URLValidationError("URL must include a hostname")

    if allow_private:
        return

    hostname = parsed.hostname.lower().rstrip(".")
    if hostname in BLOCKED_HOSTNAMES or hostname.endswith(".localhost") or hostname.endswith(".internal"):
        raise URLValidationError(f"Private/internal IPs not allowed: {hostname}")

    # Literal IP address
    try:
        literal_ip = ipaddress.ip_address(hostname)
    except ValueError:
        literal_ip = None

    if literal_ip is not None:
        if _is_forbidden_ip(literal_ip):
            raise URLValidationError(f"Private/internal IPs not allowed: {hostname}")
        return

    # Hostname: resolve and check every address (blocks internal docker names
    # such as "db" or "browserless" and DNS names pointing to private ranges)
    try:
        addresses = _resolve_host(hostname)
    except (socket.gaierror, UnicodeError, OSError) as e:
        raise URLValidationError(f"Unable to resolve hostname: {hostname}") from e

    if not addresses:
        raise URLValidationError(f"Unable to resolve hostname: {hostname}")

    for address in addresses:
        try:
            ip = ipaddress.ip_address(address.split("%", 1)[0])
        except ValueError as e:
            raise URLValidationError(f"Invalid resolved address for {hostname}") from e
        if _is_forbidden_ip(ip):
            raise URLValidationError(f"Private/internal IPs not allowed: {hostname} -> {address}")
