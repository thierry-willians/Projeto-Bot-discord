import os

import pytest

# Variáveis obrigatórias precisam existir antes de get_settings() ser chamada.
os.environ.setdefault("DISCORD_TOKEN", "test-token")
os.environ.setdefault("GUILD_ID", "111111111111111111")
os.environ.setdefault("ROLE_ID", "222222222222222222")
os.environ.setdefault("MP_ACCESS_TOKEN", "test-mp-access-token")
os.environ.setdefault("DATABASE_PATH", ":memory:")

from config.settings import get_settings  # noqa: E402
from database.connection import Database  # noqa: E402


@pytest.fixture
def settings():
    get_settings.cache_clear()
    return get_settings()


@pytest.fixture
def db():
    """Banco SQLite em memória, isolado por teste."""
    database = Database(":memory:")
    yield database
    database.close()
