"""FastAPI application: routes, middleware, static UI, and app factory.

Endpoints:
  * ``GET  /``            → the accessible single-page UI
  * ``GET  /health``      → liveness probe (no LLM)
  * ``POST /api/assist``  → context-aware guidance (rate-limited)
  * ``GET  /api/stadium`` → zone/facility metadata for the UI
"""

from __future__ import annotations

from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from src.config import AppConfig, load_config
from src.logging_conf import create_logger
from src.models.schemas import (
    MobilityRequirement,
    GuidanceResponse,
    NavigationGoal,
    StatusResponse,
    Locale,
    FanRequest,
)
from src.services.ai_client import initialize_model
from src.services.rules_engine import PathUnavailable, process_request
from src.services.security import RequestThrottle
from src.services.stadium_data import VenueData, load_venue

logger = create_logger("arenaguide")

_STATIC_DIR = Path(__file__).resolve().parent / "static"

_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Content-Security-Policy": (
        "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; "
        "connect-src 'self'; base-uri 'none'; frame-ancestors 'none'"
    ),
}


def _venue_metadata(venue: VenueData) -> dict:
    """Serialize zones/facilities and enum vocabularies for the front-end."""
    return {
        "stadium": {
            "name": venue.name,
            "fifa_name": venue.fifa_name,
            "city": venue.city,
            "capacity": venue.capacity,
        },
        # `name`/`landmark` are localized maps ({en,es,fr}); the UI picks the language.
        "zones": [
            {"id": z.id, "name": z.names, "type": z.type, "level": z.level}
            for z in venue.zones.values()
        ],
        "facilities": [
            {
                "id": f.id,
                "name": f.names,
                "type": f.type,
                "zone": f.zone,
                "accessible": f.accessible,
                "landmark": f.landmarks,
            }
            for f in venue.facilities
        ],
        "intents": [i.value for i in NavigationGoal],
        "languages": [lang.value for lang in Locale],
        "accessibility_needs": [n.value for n in MobilityRequirement],
    }


def _rate_limit_dependency(request: Request) -> None:
    """Reject requests that exceed the per-IP token-bucket budget with 429."""
    throttle: RequestThrottle = request.app.state.rate_limiter
    client_ip = request.client.host if request.client else "unknown"
    allowed, retry_after = throttle.check(client_ip)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Please slow down.",
            headers={"Retry-After": str(int(retry_after) + 1)},
        )


def create_app(config: AppConfig | None = None) -> FastAPI:
    """Application factory. Accepts an explicit ``config`` (used by tests)."""
    config = config or load_config()

    app = FastAPI(
        title="ArenaGuide",
        description="Multilingual, accessible stadium assistant for FIFA World Cup 2026.",
        version="1.0.0",
    )

    # Shared, startup-time singletons (fixtures loaded once; LLM chosen once).
    app.state.settings = config
    app.state.stadium = load_venue()
    app.state.llm = initialize_model(config)
    app.state.rate_limiter = RequestThrottle(
        config.rate_limit_capacity, config.rate_limit_refill_per_sec
    )

    # Restrictive CORS: explicit allow-list only.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.allowed_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    @app.middleware("http")
    async def add_security_headers(request: Request, call_next):
        response = await call_next(request)
        for header, value in _SECURITY_HEADERS.items():
            response.headers.setdefault(header, value)
        return response

    @app.exception_handler(PathUnavailable)
    async def _path_unavailable_handler(request: Request, exc: PathUnavailable):
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.get("/health", response_model=StatusResponse, tags=["system"])
    async def health() -> StatusResponse:
        return StatusResponse(status="ok")

    @app.get("/api/stadium", tags=["data"])
    async def stadium_metadata(request: Request) -> dict:
        return _venue_metadata(request.app.state.stadium)

    @app.post(
        "/api/assist",
        response_model=GuidanceResponse,
        dependencies=[Depends(_rate_limit_dependency)],
        tags=["assist"],
    )
    async def assist(req: FanRequest, request: Request) -> GuidanceResponse:
        venue: VenueData = request.app.state.stadium
        llm = request.app.state.llm
        response = await process_request(req, venue, llm)
        # Privacy-preserving log: goals/zones/outcome only — never the question.
        logger.info(
            "assist location=%s goal=%s needs=%s density=%s used_llm=%s",
            req.current_location,
            req.destination_intent.value,
            "+".join(n.value for n in req.accessibility_needs),
            response.crowd_level.value,
            response.used_llm,
        )
        return response

    @app.get("/", include_in_schema=False)
    async def index() -> FileResponse:
        return FileResponse(_STATIC_DIR / "index.html")

    # Serve CSS/JS. (index.html is served explicitly at "/").
    # On Vercel, static files might not be bundled directly into the function if misconfigured,
    # so we only mount the directory if it exists to prevent startup crashes.
    if _STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")

    return app


# Module-level ASGI app for `uvicorn src.main:app`.
app = create_app()
