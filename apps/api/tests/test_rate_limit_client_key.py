"""_client_key's header-priority logic — the bug this guards against: Render
fronts every deployment with Cloudflare, and without trusting CF-Connecting-IP
first, every request arriving through that proxy layer could resolve to the
same apparent IP (the proxy's own), letting one client's traffic exhaust
another client's rate-limit bucket. Hit for real in production on /register."""
from types import SimpleNamespace

from app.core.rate_limit import _client_key


def _request(headers: dict, client_host: str | None = "203.0.113.9") -> SimpleNamespace:
    client = SimpleNamespace(host=client_host) if client_host else None
    return SimpleNamespace(headers=headers, client=client)


def test_authenticated_user_keys_by_user_id_regardless_of_headers():
    req = _request({"cf-connecting-ip": "1.2.3.4"})
    assert _client_key(req, user_id="abc-123") == "user:abc-123"


def test_prefers_cf_connecting_ip_over_x_forwarded_for():
    req = _request({"cf-connecting-ip": "9.9.9.9", "x-forwarded-for": "1.1.1.1, 10.0.0.1"})
    assert _client_key(req, user_id=None) == "ip:9.9.9.9"


def test_falls_back_to_x_forwarded_for_first_hop_when_no_cf_header():
    req = _request({"x-forwarded-for": "5.5.5.5, 10.0.0.1"})
    assert _client_key(req, user_id=None) == "ip:5.5.5.5"


def test_falls_back_to_request_client_host_with_no_proxy_headers():
    req = _request({}, client_host="127.0.0.1")
    assert _client_key(req, user_id=None) == "ip:127.0.0.1"


def test_two_different_cf_connecting_ips_never_share_a_bucket():
    req_a = _request({"cf-connecting-ip": "1.2.3.4"})
    req_b = _request({"cf-connecting-ip": "5.6.7.8"})
    assert _client_key(req_a, user_id=None) != _client_key(req_b, user_id=None)
