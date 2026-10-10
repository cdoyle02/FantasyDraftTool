"""Public Streamable HTTP MCP server.

Claude uses a static bearer token in a request header. ChatGPT uses the OAuth
authorization-code flow in oauth.py and then sends the access token it received.
"""

from __future__ import annotations

import json
import os
from typing import Any
from urllib.parse import parse_qs

from starlette.responses import JSONResponse

from . import oauth
from .profiles import EspnProfile, load_http_profiles, match_profile, reset_profile, set_profile
from .server import server

_health_registered = False


def _register_health() -> None:
    global _health_registered
    if _health_registered:
        return

    @server.custom_route("/health", methods=["GET"], include_in_schema=False)
    async def health(_request: Any) -> JSONResponse:
        return JSONResponse({"status": "ok"})

    _health_registered = True


class BearerProfiles:
    """Gate /mcp with a profile token and leave /health open for Railway."""

    def __init__(self, app: Any, profiles: list[EspnProfile]) -> None:
        self.app = app
        self.profiles = profiles

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return
        path = scope.get("path") or ""
        if path == "/health":
            await self.app(scope, receive, send)
            return

        if _is_public(path):
            await _handle_public(scope, receive, send, self.profiles)
            return

        presented = _bearer_token(scope)
        origin = oauth.public_origin(scope)
        profile = match_profile(presented, self.profiles) if presented else None
        if profile is None and presented:
            profile = oauth.profile_for_access_token(presented, self.profiles, origin=origin)
        if profile is None:
            await _reject(send, "unauthorized", origin)
            return
        if not profile.config.authenticated:
            await _reject(send, "profile_unconfigured", origin)
            return

        token = set_profile(profile)
        try:
            await self.app(scope, receive, send)
        finally:
            reset_profile(token)


def _bearer_token(scope: dict[str, Any]) -> str:
    headers = scope.get("headers") or []
    for key, value in headers:
        if key.lower() == b"authorization":
            text = value.decode("latin-1")
            prefix = "bearer "
            if text.lower().startswith(prefix):
                return text[len(prefix) :].strip()
            return ""
    return ""


def _is_public(path: str) -> bool:
    return path in {"/health", "/authorize", "/token", "/register"} or path.startswith(
        "/.well-known/"
    )


async def _handle_public(
    scope: dict[str, Any],
    receive: Any,
    send: Any,
    profiles: list[EspnProfile],
) -> None:
    path = scope.get("path") or ""
    method = (scope.get("method") or "GET").upper()
    origin = oauth.public_origin(scope)
    query = _query(scope)
    if path == "/health" and method == "GET":
        await _json(send, 200, {"status": "ok"})
        return
    if path in {
        "/.well-known/oauth-protected-resource",
        "/.well-known/oauth-protected-resource/mcp",
    }:
        await _json(send, 200, oauth.protected_resource_metadata(origin))
        return
    if path == "/.well-known/oauth-authorization-server":
        await _json(send, 200, oauth.authorization_server_metadata(origin))
        return
    if path == "/register" and method == "POST":
        await _register(receive, send)
        return
    if path == "/token" and method == "POST":
        await _token(origin, receive, send)
        return
    if path == "/authorize" and method == "GET":
        await _html(send, 200, oauth.login_page(query))
        return
    if path == "/authorize" and method == "POST":
        await _authorize(origin, query, receive, send, profiles)
        return
    await _json(send, 404, {"error": "not_found"})


async def _register(receive: Any, send: Any) -> None:
    form = _parse_body(await _read_body(receive))
    redirects = form.get("redirect_uris") or []
    if isinstance(redirects, str):
        redirects = [redirects]
    if not redirects or any(not oauth.redirect_allowed(uri) for uri in redirects):
        await _json(send, 400, {"error": "invalid_redirect_uri"})
        return
    await _json(
        send,
        201,
        {
            "client_id": form.get("client_name") or "chatgpt",
            "redirect_uris": redirects,
            "token_endpoint_auth_method": "none",
            "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"],
        },
    )


async def _token(origin: str, receive: Any, send: Any) -> None:
    form = _parse_body(await _read_body(receive))
    resource = form.get("resource") or oauth.resource_url(origin)
    grant = form.get("grant_type") or ""
    issued: dict[str, Any] | None
    if grant == "authorization_code":
        issued = oauth.exchange_authorization_code(
            code=form.get("code") or "",
            verifier=form.get("code_verifier") or "",
            client_id=form.get("client_id") or "",
            redirect_uri=form.get("redirect_uri") or "",
            resource=resource,
            issuer=origin,
        )
    elif grant == "refresh_token":
        issued = oauth.exchange_refresh_token(form.get("refresh_token") or "", resource, origin)
    else:
        issued = None
    if issued is None:
        await _json(send, 400, {"error": "invalid_grant"})
        return
    await _json(send, 200, issued)


async def _authorize(
    origin: str,
    query: dict[str, str],
    receive: Any,
    send: Any,
    profiles: list[EspnProfile],
) -> None:
    form = {**query, **_parse_body(await _read_body(receive))}
    redirect_uri = form.get("redirect_uri") or ""
    if not oauth.redirect_allowed(redirect_uri):
        await _html(send, 400, oauth.login_page(form, error="That redirect URL is not allowed."))
        return
    person = form.get("person") or ""
    if not oauth.password_matches(person, form.get("password") or ""):
        await _html(send, 401, oauth.login_page(form, error="Wrong password."))
        return
    selected = next((item for item in profiles if item.name == person), None)
    if selected is None or not selected.config.authenticated:
        await _html(send, 401, oauth.login_page(form, error="That login is not ready yet."))
        return
    if form.get("code_challenge_method") != "S256" or not form.get("code_challenge"):
        await _redirect_error(send, redirect_uri, form, origin, "invalid_request")
        return
    resource = form.get("resource") or oauth.resource_url(origin)
    code = oauth.issue_code(
        person=person,
        client_id=form.get("client_id") or "",
        redirect_uri=redirect_uri,
        code_challenge=form.get("code_challenge") or "",
        resource=resource,
    )
    location = oauth.with_query(
        redirect_uri,
        {"code": code, "state": form.get("state") or "", "iss": origin},
    )
    await _redirect(send, location)


async def _redirect_error(
    send: Any,
    redirect_uri: str,
    form: dict[str, str],
    origin: str,
    error: str,
) -> None:
    location = oauth.with_query(
        redirect_uri,
        {"error": error, "state": form.get("state") or "", "iss": origin},
    )
    await _redirect(send, location)


def _query(scope: dict[str, Any]) -> dict[str, str]:
    parsed = parse_qs((scope.get("query_string") or b"").decode(), keep_blank_values=True)
    return {key: values[-1] for key, values in parsed.items()}


def _parse_body(raw: bytes) -> dict[str, Any]:
    text = raw.decode()
    if not text:
        return {}
    if text.lstrip().startswith("{"):
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            return {}
        return payload if isinstance(payload, dict) else {}
    parsed = parse_qs(text, keep_blank_values=True)
    return {key: values[-1] if len(values) == 1 else values for key, values in parsed.items()}


async def _read_body(receive: Any) -> bytes:
    chunks: list[bytes] = []
    while True:
        message = await receive()
        if message["type"] == "http.disconnect":
            break
        chunks.append(message.get("body") or b"")
        if not message.get("more_body", False):
            break
    return b"".join(chunks)


async def _reject(send: Any, error: str, origin: str) -> None:
    body = json.dumps({"error": error}).encode()
    challenge = (
        'Bearer resource_metadata="'
        + oauth.metadata_url(origin)
        + '", scope="'
        + oauth.SCOPE
        + '"'
    )
    await send(
        {
            "type": "http.response.start",
            "status": 401,
            "headers": [
                [b"content-type", b"application/json"],
                [b"content-length", str(len(body)).encode()],
                [b"www-authenticate", challenge.encode()],
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})


async def _json(send: Any, status: int, payload: dict[str, Any]) -> None:
    body = json.dumps(payload).encode()
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [
                [b"content-type", b"application/json"],
                [b"content-length", str(len(body)).encode()],
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})


async def _html(send: Any, status: int, page: str) -> None:
    body = page.encode()
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [
                [b"content-type", b"text/html; charset=utf-8"],
                [b"content-length", str(len(body)).encode()],
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})


async def _redirect(send: Any, location: str) -> None:
    await send(
        {
            "type": "http.response.start",
            "status": 302,
            "headers": [
                [b"location", location.encode()],
                [b"content-length", b"0"],
            ],
        }
    )
    await send({"type": "http.response.body", "body": b""})


def create_app() -> BearerProfiles:
    _register_health()
    profiles = load_http_profiles()
    # host 0.0.0.0 keeps DNS-rebinding protection off so Railway's public Host
    # header is accepted. The bearer token is the access check.
    inner = server.streamable_http_app(
        streamable_http_path="/mcp",
        json_response=True,
        stateless_http=True,
        host="0.0.0.0",
    )
    return BearerProfiles(inner, profiles)


def main() -> None:
    import uvicorn

    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(create_app(), host="0.0.0.0", port=port)
