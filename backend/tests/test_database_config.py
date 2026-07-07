import pytest

from backend.config import Settings


def settings(**overrides) -> Settings:
    defaults = {
        "DATABASE_URL": "postgresql://legacy/example",
        "SUPABASE_DATABASE_URL": None,
        "POSTGRES_DATABASE_URL": None,
        "DATABASE_URL_SYNC": None,
        "SUPABASE_DATABASE_URL_SYNC": None,
        "POSTGRES_DATABASE_URL_SYNC": None,
    }
    defaults.update(overrides)
    return Settings(_env_file=None, **defaults)


def test_supabase_is_default_database_provider():
    config = settings(SUPABASE_DATABASE_URL="postgresql://supabase/example")

    assert config.database_provider == "supabase"
    assert config.active_database_url == "postgresql://supabase/example"


def test_postgres_provider_uses_postgres_url():
    config = settings(
        DATABASE_PROVIDER="postgres",
        POSTGRES_DATABASE_URL="postgresql://localhost/example",
    )

    assert config.database_provider == "postgresql"
    assert config.active_database_url == "postgresql://localhost/example"


def test_selected_provider_falls_back_to_legacy_database_url():
    config = settings(DATABASE_PROVIDER="supabase", SUPABASE_DATABASE_URL="")

    assert config.active_database_url == "postgresql://legacy/example"


def test_invalid_database_provider_raises_clear_error():
    config = settings(DATABASE_PROVIDER="sqlite")

    with pytest.raises(ValueError, match="DATABASE_PROVIDER"):
        _ = config.database_provider
