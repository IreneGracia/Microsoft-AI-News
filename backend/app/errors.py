"""
Error responses in RFC 7807 "Problem Details" format.

Why RFC 7807: docs/api.md §1 picks it as the standard error shape. Every
error body looks the same — clients parse it once and handle it uniformly.

Example response body:

    {
      "type": "https://docs.example/errors/preference-invalid",
      "title": "Invalid preference value",
      "status": 422,
      "detail": "Topic 'quantum' is not in the taxonomy",
      "instance": "/api/v1/me/preferences"
    }

Usage in a router:

    from app.errors import problem
    raise problem(status=404, title="User not found")
"""

from fastapi import HTTPException
from fastapi.responses import JSONResponse


# Content type required by RFC 7807.
PROBLEM_CONTENT_TYPE = "application/problem+json"


def problem(
    *,
    status: int,
    title: str,
    detail: str | None = None,
    type_: str = "about:blank",
) -> HTTPException:
    """
    Build an HTTPException whose response body is an RFC 7807 problem doc.

    Raise the return value — FastAPI's exception handler converts it to a JSON
    response. We attach the response body via the `detail` kwarg so it's
    serialized verbatim.
    """
    body = {
        "type": type_,
        "title": title,
        "status": status,
    }
    if detail is not None:
        body["detail"] = detail

    # `detail` here is what FastAPI puts in the response body; passing a dict
    # gives us full control over the shape.
    return HTTPException(status_code=status, detail=body)


def problem_response(
    *,
    status: int,
    title: str,
    detail: str | None = None,
    type_: str = "about:blank",
) -> JSONResponse:
    """
    Direct JSONResponse variant — used by custom exception handlers in main.py
    where raising isn't appropriate (e.g. the 422 validation handler).
    """
    body: dict = {"type": type_, "title": title, "status": status}
    if detail is not None:
        body["detail"] = detail
    return JSONResponse(
        status_code=status,
        content=body,
        media_type=PROBLEM_CONTENT_TYPE,
    )
