"""
Tests for URL validation and security.
"""

import socket

import pytest

from app import url_validation
from app.url_validation import URLValidationError, validate_url


def _fake_resolve(hostname: str) -> list[str]:
    """Deterministic DNS for tests (no network access needed)."""
    if hostname == "127.1":
        return ["127.0.0.1"]
    if hostname.startswith("private."):
        return ["10.0.0.5"]
    if hostname.startswith("mixed."):
        return ["93.184.216.34", "192.168.1.10"]
    if hostname.startswith("mapped."):
        return ["::ffff:169.254.169.254"]
    if hostname in {"db", "browserless"} or hostname.startswith("unresolvable."):
        raise socket.gaierror("Name or service not known")
    return ["93.184.216.34"]


@pytest.fixture(autouse=True)
def fake_dns(monkeypatch):
    monkeypatch.setattr(url_validation, "_resolve_host", _fake_resolve)


class TestURLValidation:
    """Test URL validation for security."""

    def test_valid_https_url(self):
        """Test that valid HTTPS URLs pass validation."""
        validate_url("https://example.com/product")
        # Should not raise

    def test_valid_http_url(self):
        """Test that valid HTTP URLs pass validation."""
        validate_url("http://example.com/product")
        # Should not raise

    def test_empty_url(self):
        """Test that empty URLs are rejected."""
        with pytest.raises(URLValidationError, match="non-empty string"):
            validate_url("")

    def test_none_url(self):
        """Test that None URLs are rejected."""
        with pytest.raises(URLValidationError, match="non-empty string"):
            validate_url(None)

    def test_missing_scheme(self):
        """Test that URLs without scheme are rejected."""
        with pytest.raises(URLValidationError, match="must include a scheme"):
            validate_url("example.com/product")

    def test_blocked_scheme_file(self):
        """Test that file:// URLs are blocked."""
        with pytest.raises(URLValidationError, match="Blocked URL scheme"):
            validate_url("file:///etc/passwd")

    def test_blocked_scheme_javascript(self):
        """Test that javascript: URLs are blocked."""
        with pytest.raises(URLValidationError, match="Blocked URL scheme"):
            validate_url("javascript:alert(1)")

    def test_blocked_scheme_data(self):
        """Test that data: URLs are blocked."""
        with pytest.raises(URLValidationError, match="Blocked URL scheme"):
            validate_url("data:text/html,<script>alert(1)</script>")

    def test_blocked_scheme_ftp(self):
        """Test that FTP URLs are blocked."""
        with pytest.raises(URLValidationError, match="Blocked URL scheme"):
            validate_url("ftp://example.com/file")

    def test_localhost_blocked(self):
        """Test that localhost is blocked."""
        with pytest.raises(URLValidationError, match="Private/internal IPs"):
            validate_url("http://localhost:8000/")

    def test_127_0_0_1_blocked(self):
        """Test that 127.0.0.1 is blocked."""
        with pytest.raises(URLValidationError, match="Private/internal IPs"):
            validate_url("http://127.0.0.1:8000/")

    def test_private_ip_10_blocked(self):
        """Test that 10.x.x.x addresses are blocked."""
        with pytest.raises(URLValidationError, match="Private/internal IPs"):
            validate_url("http://10.0.0.1/")

    def test_private_ip_192_blocked(self):
        """Test that 192.168.x.x addresses are blocked."""
        with pytest.raises(URLValidationError, match="Private/internal IPs"):
            validate_url("http://192.168.1.1/")

    def test_private_ip_172_blocked(self):
        """Test that 172.16-31.x.x addresses are blocked."""
        with pytest.raises(URLValidationError, match="Private/internal IPs"):
            validate_url("http://172.16.0.1/")

    def test_link_local_blocked(self):
        """Test that link-local addresses (169.254.x.x) are blocked."""
        with pytest.raises(URLValidationError, match="Private/internal IPs"):
            validate_url("http://169.254.0.1/")

    def test_ipv6_loopback_blocked(self):
        """Test that IPv6 loopback (::1) is blocked."""
        with pytest.raises(URLValidationError, match="Private/internal IPs"):
            validate_url("http://[::1]:8000/")

    def test_allow_private_param(self):
        """Test that allow_private parameter works."""
        # Should not raise when allow_private=True
        validate_url("http://localhost:8000/", allow_private=True)
        validate_url("http://127.0.0.1:8000/", allow_private=True)
        validate_url("http://192.168.1.1/", allow_private=True)

    def test_missing_hostname(self):
        """Test that URLs without hostname are rejected."""
        with pytest.raises(URLValidationError, match="must include a hostname"):
            validate_url("http:///path")

    def test_url_with_query_params(self):
        """Test that URLs with query parameters work."""
        validate_url("https://example.com/product?id=123&ref=abc")
        # Should not raise

    def test_url_with_fragment(self):
        """Test that URLs with fragments work."""
        validate_url("https://example.com/product#section")
        # Should not raise

    def test_url_with_port(self):
        """Test that URLs with ports work."""
        validate_url("https://example.com:8443/product")
        # Should not raise

    def test_international_domain(self):
        """Test that international domains work."""
        validate_url("https://例え.jp/product")
        # Should not raise


class TestSSRFPrevention:
    """Test SSRF attack prevention."""

    def test_ssrf_localhost_variants(self):
        """Test various localhost representations."""
        localhost_variants = [
            "http://localhost/",
            "http://127.0.0.1/",
            "http://127.1/",
            "http://0.0.0.0/",
        ]

        for url in localhost_variants:
            with pytest.raises(URLValidationError):
                validate_url(url)

    def test_ssrf_private_networks(self):
        """Test private network ranges."""
        private_ranges = [
            "http://10.1.2.3/",
            "http://172.16.0.1/",
            "http://172.31.255.255/",
            "http://192.168.0.1/",
            "http://169.254.169.254/",  # AWS metadata
        ]

        for url in private_ranges:
            with pytest.raises(URLValidationError):
                validate_url(url)

    def test_public_ips_allowed(self):
        """Test that public IPs are allowed."""
        public_ips = [
            "http://8.8.8.8/",
            "http://1.1.1.1/",
            "http://142.250.185.78/",  # Google
        ]

        for url in public_ips:
            validate_url(url)
            # Should not raise

    def test_hostname_resolving_to_private_ip_blocked(self):
        """DNS names pointing to private ranges are blocked (DNS-based SSRF)."""
        with pytest.raises(URLValidationError, match="Private/internal IPs"):
            validate_url("http://private.attacker.example/")

    def test_hostname_with_any_private_record_blocked(self):
        """A single private A record is enough to block."""
        with pytest.raises(URLValidationError, match="Private/internal IPs"):
            validate_url("http://mixed.attacker.example/")

    def test_ipv4_mapped_ipv6_blocked(self):
        """IPv4-mapped IPv6 addresses are checked against IPv4 ranges."""
        with pytest.raises(URLValidationError, match="Private/internal IPs"):
            validate_url("http://[::ffff:127.0.0.1]/")
        with pytest.raises(URLValidationError, match="Private/internal IPs"):
            validate_url("http://mapped.attacker.example/")

    def test_metadata_and_internal_hostnames_blocked(self):
        """Cloud metadata / internal hostnames are blocked."""
        for url in [
            "http://metadata.google.internal/",
            "http://foo.localhost/",
            "http://[fd00::1]/",
            "http://100.64.0.1/",
        ]:
            with pytest.raises(URLValidationError):
                validate_url(url)

    def test_internal_docker_hostnames_blocked(self):
        """Unresolvable / internal service names are rejected."""
        for url in ["http://db:5432/", "http://browserless:3000/"]:
            with pytest.raises(URLValidationError):
                validate_url(url)
