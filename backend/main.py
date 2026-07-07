"""
main.py  –  FastAPI application entry point
Run from the project root with:  uvicorn backend.main:app --reload --port 8000
"""
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, RedirectResponse

from backend.config import settings
from backend.database import connect_db, disconnect_db, database
from backend.routers import atm, mobile, transactions, enrollment

# ── Logging ───────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

NO_STORE_HEADERS = {"Cache-Control": "no-store, max-age=0"}


# ── Lifespan (startup / shutdown) ─────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Connecting to database...")
    app.state.db_connected = False
    app.state.db_error = None
    try:
        await connect_db()
        app.state.db_connected = True
        logger.info("Database connected.")
    except Exception as exc:
        app.state.db_error = str(exc)
        logger.error("Database connection failed during startup: %s", exc)
    yield
    if database.is_connected:
        await disconnect_db()
        logger.info("Database disconnected.")


# ── App ───────────────────────────────────────────────────
app = FastAPI(
    title="ATM Voice + Face Authentication System",
    description=(
        "Multi-factor ATM authentication: "
        "Card + PIN → Voice Verification → SMS Link → Face Recognition → Transactions"
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Static files ──────────────────────────────────────────
frontend_path = Path(__file__).parent.parent / "frontend"
if frontend_path.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_path)), name="static")

# ── Routers ───────────────────────────────────────────────
app.include_router(atm.router)
app.include_router(mobile.router)
app.include_router(transactions.router)
app.include_router(enrollment.router)


# ── Root redirects ────────────────────────────────────────
@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse(url="/atm")


@app.get("/atm", response_class=HTMLResponse, include_in_schema=False)
async def serve_atm():
    html_path = Path(__file__).parent.parent / "frontend" / "atm" / "index.html"
    if html_path.exists():
        return HTMLResponse(html_path.read_text(encoding="utf-8"), headers=NO_STORE_HEADERS)
    return HTMLResponse("<h2>ATM frontend not found</h2>", status_code=404, headers=NO_STORE_HEADERS)


@app.get("/mobile", response_class=HTMLResponse, include_in_schema=False)
async def serve_mobile():
    html_path = Path(__file__).parent.parent / "frontend" / "mobile" / "face_auth.html"
    if html_path.exists():
        return HTMLResponse(html_path.read_text(encoding="utf-8"), headers=NO_STORE_HEADERS)
    return HTMLResponse("<h2>Mobile frontend not found</h2>", status_code=404, headers=NO_STORE_HEADERS)


@app.get("/verify/face/{token}", response_class=HTMLResponse, include_in_schema=False)
async def serve_face_verify(token: str):
    return RedirectResponse(url=f"/mobile/face-auth?token={token}")

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "version": "1.0.0",
        "database_connected": database.is_connected,
    }


@app.get("/diagnostics")
async def diagnostics():
    return {
        "status": "ok",
        "database_connected": database.is_connected,
        "database_error": getattr(app.state, "db_error", None),
        "public_base_url_configured": bool(settings.PUBLIC_BASE_URL),
        "sms_provider": settings.SMS_PROVIDER,
        "voice_auth_enabled": settings.ENABLE_VOICE_AUTH,
        "cors_origins": settings.cors_origins_list,
    }
