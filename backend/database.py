"""
database.py  –  Async PostgreSQL connection via databases + SQLAlchemy core
"""
import databases
import ssl
import sqlalchemy
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from sqlalchemy import (
    MetaData, Table, Column, String, Boolean, Float,
    DateTime, Numeric, LargeBinary, Text, ForeignKey
)
from sqlalchemy.dialects.postgresql import UUID
from .config import settings


def _query_options(url: str) -> dict[str, str]:
    return dict(parse_qsl(urlsplit(url).query, keep_blank_values=True))


def _with_query_options(url: str, updates: dict[str, str | None]) -> str:
    parts = urlsplit(url)
    options = dict(parse_qsl(parts.query, keep_blank_values=True))
    for key, value in updates.items():
        if value is None:
            options.pop(key, None)
        else:
            options[key] = value
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(options), parts.fragment))


def _async_database_url() -> str:
    url = settings.active_database_url
    options = _query_options(url)
    if options.get("ssl") == "true" or options.get("sslmode") in {"require", "prefer"}:
        url = _with_query_options(url, {"ssl": None, "sslmode": None})
    return url


def _unverified_ssl_context() -> ssl.SSLContext:
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    return context


def _database_options() -> dict:
    options = _query_options(settings.active_database_url)
    database_options = {
        "min_size": settings.DB_POOL_MIN_SIZE,
        "max_size": settings.DB_POOL_MAX_SIZE,
    }
    if "statement_cache_size" in options:
        database_options["statement_cache_size"] = int(options["statement_cache_size"])
    if options.get("ssl") == "true" or options.get("sslmode") in {"require", "prefer"}:
        database_options["ssl"] = _unverified_ssl_context()
    return database_options


# ── Async database (for runtime queries) ─────────────────
database = databases.Database(_async_database_url(), **_database_options())

# ── Sync engine (for migrations / startup) ───────────────
def _sync_database_url() -> str:
    url = settings.active_database_url_sync or settings.active_database_url
    options = _query_options(url)
    if options.get("ssl") == "true" and "sslmode" not in options:
        url = _with_query_options(url, {"ssl": None, "sslmode": "require"})
    if "statement_cache_size" in options:
        url = _with_query_options(url, {"statement_cache_size": None})
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


_sync_engine = None


def get_sync_engine():
    """
    Create the sync SQLAlchemy engine only when explicitly needed.
    Vercel/serverless runtime uses the async database path and may not install
    sync-only drivers such as psycopg.
    """
    global _sync_engine
    if _sync_engine is None:
        _sync_engine = sqlalchemy.create_engine(_sync_database_url())
    return _sync_engine


sync_engine = None

metadata = MetaData()

# ── Table reflections (mirrors schema.sql) ────────────────

users = Table(
    "users", metadata,
    Column("id",             UUID, primary_key=True),
    Column("full_name",      String(100), nullable=False),
    Column("account_number", String(20),  unique=True, nullable=False),
    Column("phone_number",   String(20),  nullable=False),
    Column("card_number",    String(20),  unique=True, nullable=False),
    Column("pin_hash",       Text,        nullable=False),
    Column("voice_sample",   LargeBinary),
    Column("face_encoding",  LargeBinary),
    Column("is_active",      Boolean, default=True),
    Column("created_at",     DateTime(timezone=True)),
    Column("updated_at",     DateTime(timezone=True)),
    schema="atm_schema",  # ← ADD THIS
)

accounts = Table(
    "accounts", metadata,
    Column("id",           UUID, primary_key=True),
    Column("user_id",      UUID, ForeignKey("atm_schema.users.id"), nullable=False),
    Column("account_type", String(20), default="savings"),
    Column("balance",      Numeric(15, 2), default=0.00),
    Column("currency",     String(5), default="NGN"),
    Column("is_frozen",    Boolean, default=False),
    Column("created_at",   DateTime(timezone=True)),
    Column("updated_at",   DateTime(timezone=True)),
    schema="atm_schema",  # ← ADD THIS
)

auth_sessions = Table(
    "auth_sessions", metadata,
    Column("id",                UUID, primary_key=True),
    Column("user_id",           UUID, ForeignKey("atm_schema.users.id")),
    Column("card_number",       String(20), nullable=False),
    Column("session_token",     Text, unique=True, nullable=False),
    Column("face_token",        Text, unique=True),
    Column("stage",             String(30), default="card_inserted"),
    Column("voice_score",       Float),
    Column("face_score",        Float),
    Column("sms_sent_at",       DateTime(timezone=True)),
    Column("voice_verified_at", DateTime(timezone=True)),
    Column("face_verified_at",  DateTime(timezone=True)),
    Column("authenticated_at",  DateTime(timezone=True)),
    Column("expires_at",        DateTime(timezone=True), nullable=False),
    Column("ip_address",        String(50)),
    Column("user_agent",        Text),
    Column("created_at",        DateTime(timezone=True)),
    schema="atm_schema",  # ← ADD THIS
)

transactions = Table(
    "transactions", metadata,
    Column("id",                UUID, primary_key=True),
    Column("session_id",        UUID, ForeignKey("atm_schema.auth_sessions.id")),
    Column("account_id",        UUID, ForeignKey("atm_schema.accounts.id"), nullable=False),
    Column("type",              String(20), nullable=False),
    Column("amount",            Numeric(15, 2)),
    Column("recipient_account", String(20)),
    Column("description",       Text),
    Column("status",            String(20), default="pending"),
    Column("created_at",        DateTime(timezone=True)),
    schema="atm_schema",  # ← ADD THIS
)

auth_logs = Table(
    "auth_logs", metadata,
    Column("id",         UUID, primary_key=True),
    Column("session_id", UUID, ForeignKey("atm_schema.auth_sessions.id")),
    Column("user_id",    UUID, ForeignKey("atm_schema.users.id")),
    Column("event",      String(50), nullable=False),
    Column("success",    Boolean, nullable=False),
    Column("score",      Float),
    Column("detail",     Text),
    Column("ip_address", String(50)),
    Column("created_at", DateTime(timezone=True)),
    schema="atm_schema",  # ← ADD THIS
)

async def connect_db():
    await database.connect()


async def disconnect_db():
    await database.disconnect()
