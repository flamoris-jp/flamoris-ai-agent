"""Versioned internal JSON adapter over the same Agent domain service as MCP."""

import json

from starlette.responses import JSONResponse
from starlette.routing import Route

MAX_BODY_BYTES = 131072


def operations(service):
    names = ["health"]
    if getattr(service, "shared_principals", False):
        names.extend(["sessions.open", "ask_scoped", "ask_availability"])
        if getattr(service, "settings_enabled", False):
            names.extend(
                [
                    "sessions.continue",
                    "models.allowed",
                    "personality.get",
                    "personality.history",
                    "personality.save",
                ]
            )
    else:
        names.append("ask")
    return names


def _unique_object(pairs):
    values = {}
    for key, value in pairs:
        if key in values:
            raise ValueError("duplicate_key")
        values[key] = value
    return values


def _nonfinite(value):
    raise ValueError("nonfinite_value")


async def request_body(request):
    if request.headers.get("content-type", "").split(";", 1)[0].strip() != "application/json":
        return None, JSONResponse(
            {"ok": False, "error": {"code": "invalid_input"}}, status_code=415
        )
    body = bytearray()
    async for part in request.stream():
        if len(body) + len(part) > MAX_BODY_BYTES:
            return None, JSONResponse(
                {"ok": False, "error": {"code": "input_too_large"}}, status_code=413
            )
        body.extend(part)
    try:
        data = json.loads(body, object_pairs_hook=_unique_object, parse_constant=_nonfinite)
        if type(data) is not dict:
            raise ValueError()
        return data, None
    except (ValueError, UnicodeError, RecursionError):
        return None, JSONResponse(
            {"ok": False, "error": {"code": "invalid_input"}}, status_code=400
        )


def routes(service):
    async def health(request):
        return JSONResponse(service.health())

    async def capabilities(request):
        return JSONResponse({"ok": True, "api_version": 1, "operations": operations(service)})

    result = [
        Route("/api/v1/health", health, methods=["GET"]),
        Route("/api/v1/capabilities", capabilities, methods=["GET"]),
    ]

    calls = {
        "ask": ("ask", service.ask),
        "sessions.open": ("sessions/open", getattr(service, "open_session", None)),
        "sessions.continue": ("sessions/continue", getattr(service, "continue_session", None)),
        "ask_scoped": ("ask-scoped", getattr(service, "ask_scoped", None)),
        "ask_availability": ("ask-availability", getattr(service, "availability", None)),
    }
    for operation in operations(service):
        if operation == "health":
            continue
        if operation in calls:
            path, method = calls[operation]
        else:
            category, name = operation.split(".")
            path = category + "/" + name
            method = None

        def endpoint(method=method, operation=operation):
            async def call(request):
                data, error = await request_body(request)
                if error is not None:
                    return error
                if method is not None:
                    response = await method(data)
                else:
                    name = {"models.allowed": "models"}.get(operation, operation.split(".")[1])
                    response = await service.settings_operation(name, data)
                return JSONResponse(response)

            return call

        result.append(Route("/api/v1/" + path, endpoint(), methods=["POST"]))
    return result
