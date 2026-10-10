"""OAuth 2.1 authorization server for ChatGPT custom apps.

ChatGPT cannot store a static bearer header. It discovers this server from
protected-resource metadata, sends the user through an authorization-code
flow with PKCE S256, then calls /mcp with the access token it receives.

Claude keeps using the static profile tokens. Access tokens issued here are
separate and name the same Michael or Katie ESPN profile.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import html
import json
import os
import time
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from .profiles import EspnProfile

CODE_TTL_SECONDS = 600
ACCESS_TTL_SECONDS = 60 * 60
REFRESH_TTL_SECONDS = 30 * 24 * 60 * 60
SCOPE = "espn"

_ALLOWED_REDIRECT_PREFIXES = (
    "https://chatgpt.com/connector_platform_oauth_redirect",
    "https://chatgpt.com/connector/oauth/",
    "https://claude.ai/api/mcp/auth_callback",
    "http://127.0.0.1",
    "http://localhost",
)


def public_origin(scope: dict[str, Any] | None = None) -> str:
    configured = os.environ.get("MCP_PUBLIC_URL", "").strip().rstrip("/")
    if configured:
        return configured
    headers = {
        key.decode().lower(): value.decode()
        for key, value in (scope or {}).get("headers") or []
    }
    proto = headers.get("x-forwarded-proto", "http")
    host = headers.get("x-forwarded-host") or headers.get("host") or "localhost"
    return f"{proto}://{host}"


def resource_url(origin: str) -> str:
    return f"{origin.rstrip('/')}/mcp"


def metadata_url(origin: str) -> str:
    return f"{origin.rstrip('/')}/.well-known/oauth-protected-resource/mcp"


def _secret() -> bytes | None:
    raw = os.environ.get("MCP_AUTH_TOKEN", "").strip()
    return raw.encode() if raw else None


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _b64decode(text: str) -> bytes:
    padding = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + padding)


def _sign(payload: dict[str, Any]) -> str:
    secret = _secret()
    if secret is None:
        raise RuntimeError("MCP_AUTH_TOKEN must be set to sign OAuth tokens.")
    body = _b64(json.dumps(payload, separators=(",", ":")).encode())
    signature = hmac.new(secret, body.encode(), hashlib.sha256).digest()
    return f"{body}.{_b64(signature)}"


def _read(token: str) -> dict[str, Any] | None:
    secret = _secret()
    if secret is None or token.count(".") != 1:
        return None
    body, signature = token.split(".", 1)
    expected = hmac.new(secret, body.encode(), hashlib.sha256).digest()
    try:
        presented = _b64decode(signature)
    except ValueError:
        return None
    if not hmac.compare_digest(expected, presented):
        return None
    try:
        payload = json.loads(_b64decode(body))
    except (ValueError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    expires = payload.get("exp")
    if not isinstance(expires, int) or expires < int(time.time()):
        return None
    return payload


def s256_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode()).digest()
    return _b64(digest)


def redirect_allowed(redirect_uri: str) -> bool:
    return any(redirect_uri.startswith(prefix) for prefix in _ALLOWED_REDIRECT_PREFIXES)


def login_password(person: str) -> str | None:
    if person == "michael":
        value = os.environ.get("MCP_LOGIN_PASSWORD", "")
    elif person == "katie":
        value = os.environ.get("MCP_LOGIN_PASSWORD_KATIE", "")
    else:
        return None
    return value.strip() or None


def password_matches(person: str, presented: str) -> bool:
    expected = login_password(person)
    if expected is None or not presented or len(presented) != len(expected):
        return False
    return hmac.compare_digest(presented, expected)


def protected_resource_metadata(origin: str) -> dict[str, Any]:
    return {
        "resource": resource_url(origin),
        "authorization_servers": [origin],
        "scopes_supported": [SCOPE],
        "bearer_methods_supported": ["header"],
    }


def authorization_server_metadata(origin: str) -> dict[str, Any]:
    return {
        "issuer": origin,
        "authorization_endpoint": f"{origin}/authorize",
        "token_endpoint": f"{origin}/token",
        "registration_endpoint": f"{origin}/register",
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code", "refresh_token"],
        "code_challenge_methods_supported": ["S256"],
        "token_endpoint_auth_methods_supported": ["none"],
        "client_id_metadata_document_supported": True,
        "authorization_response_iss_parameter_supported": True,
        "scopes_supported": [SCOPE],
    }


def issue_code(
    *,
    person: str,
    client_id: str,
    redirect_uri: str,
    code_challenge: str,
    resource: str,
) -> str:
    return _sign(
        {
            "typ": "code",
            "sub": person,
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "code_challenge": code_challenge,
            "resource": resource,
            "exp": int(time.time()) + CODE_TTL_SECONDS,
        }
    )


def issue_access_token(person: str, resource: str, issuer: str) -> str:
    return _sign(
        {
            "typ": "access",
            "sub": person,
            "aud": resource,
            "iss": issuer,
            "scope": SCOPE,
            "exp": int(time.time()) + ACCESS_TTL_SECONDS,
        }
    )


def issue_refresh_token(person: str, resource: str) -> str:
    return _sign(
        {
            "typ": "refresh",
            "sub": person,
            "aud": resource,
            "exp": int(time.time()) + REFRESH_TTL_SECONDS,
        }
    )


def profile_for_access_token(
    token: str,
    profiles: list[EspnProfile],
    *,
    origin: str,
) -> EspnProfile | None:
    payload = _read(token)
    if payload is None or payload.get("typ") != "access":
        return None
    if payload.get("iss") != origin or payload.get("aud") != resource_url(origin):
        return None
    subject = payload.get("sub")
    for profile in profiles:
        if profile.name == subject:
            return profile
    return None


def exchange_authorization_code(
    *,
    code: str,
    verifier: str,
    client_id: str,
    redirect_uri: str,
    resource: str,
    issuer: str,
) -> dict[str, Any] | None:
    payload = _read(code)
    if payload is None or payload.get("typ") != "code":
        return None
    if payload.get("client_id") != client_id or payload.get("redirect_uri") != redirect_uri:
        return None
    if payload.get("resource") != resource:
        return None
    if payload.get("code_challenge") != s256_challenge(verifier):
        return None
    person = str(payload.get("sub") or "")
    return _token_response(person, resource, issuer)


def exchange_refresh_token(token: str, resource: str, issuer: str) -> dict[str, Any] | None:
    payload = _read(token)
    if payload is None or payload.get("typ") != "refresh":
        return None
    if payload.get("aud") != resource:
        return None
    person = str(payload.get("sub") or "")
    return _token_response(person, resource, issuer)


def _token_response(person: str, resource: str, issuer: str) -> dict[str, Any]:
    return {
        "access_token": issue_access_token(person, resource, issuer),
        "token_type": "Bearer",
        "expires_in": ACCESS_TTL_SECONDS,
        "refresh_token": issue_refresh_token(person, resource),
        "scope": SCOPE,
    }


def with_query(url: str, params: dict[str, str]) -> str:
    parts = urlparse(url)
    current = parse_qs(parts.query, keep_blank_values=True)
    flat = {key: values[-1] for key, values in current.items()}
    flat.update(params)
    return urlunparse(parts._replace(query=urlencode(flat)))


def login_page(params: dict[str, str], *, error: str = "") -> str:
    people = [name for name in ("michael", "katie") if login_password(name)]
    options = "".join(
        f'<option value="{html.escape(name)}">{html.escape(name.title())}</option>'
        for name in people
    )
    hidden = "".join(
        f'<input type="hidden" name="{html.escape(key)}" value="{html.escape(value)}">'
        for key, value in params.items()
        if key
        in {
            "client_id",
            "redirect_uri",
            "state",
            "code_challenge",
            "code_challenge_method",
            "resource",
            "scope",
        }
    )
    message = f"<p>{html.escape(error)}</p>" if error else ""
    return f"""<!doctype html>
<html lang="en">
<head>
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Fantasy Draft sign in</title>
</head>
<body>
<main>
<h1>Fantasy Draft</h1>
{message}
<form method="post" action="/authorize">
<label>Who is signing in <select name="person">{options}</select></label>
<label>Password
<input name="password" type="password" autocomplete="current-password" required>
</label>
{hidden}
<button type="submit">Continue</button>
</form>
</main>
</body>
</html>
"""
