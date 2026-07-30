import os
from dataclasses import dataclass
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()

REQUIRED_VARS = ["DISCORD_TOKEN", "GUILD_ID", "ROLE_ID", "MP_ACCESS_TOKEN"]


@dataclass(frozen=True)
class Settings:
    DISCORD_TOKEN: str
    GUILD_ID: int
    ROLE_ID: int
    MP_ACCESS_TOKEN: str

    SUBSCRIPTION_PRICE: float = 100.00
    SUBSCRIPTION_DAYS: int = 30

    DATABASE_PATH: str = "subscriptions.db"

    WEBHOOK_HOST: str = "0.0.0.0"
    WEBHOOK_PORT: int = 8000

    PAYER_EMAIL_DOMAIN: str = "discord-subscriber.local"

    ADMIN_KEY: str = ""

    ADMIN_DISCORD_ID: str = "1066862919960231986"


@lru_cache
def get_settings() -> Settings:
    missing = [v for v in REQUIRED_VARS if not os.getenv(v)]
    if missing:
        raise RuntimeError(
            "Variáveis de ambiente ausentes: "
            + ", ".join(missing)
            + ". Configure o arquivo .env (veja .env.example)."
        )

    try:
        guild_id = int(os.environ["GUILD_ID"])
        role_id = int(os.environ["ROLE_ID"])
    except ValueError as exc:
        raise RuntimeError("GUILD_ID e ROLE_ID devem ser números inteiros.") from exc

    return Settings(
        DISCORD_TOKEN=os.environ["DISCORD_TOKEN"],
        GUILD_ID=guild_id,
        ROLE_ID=role_id,
        MP_ACCESS_TOKEN=os.environ["MP_ACCESS_TOKEN"],
        SUBSCRIPTION_PRICE=float(os.getenv("SUBSCRIPTION_PRICE", "100.00")),
        SUBSCRIPTION_DAYS=int(os.getenv("SUBSCRIPTION_DAYS", "30")),
        DATABASE_PATH=os.getenv("DATABASE_PATH", "subscriptions.db"),
        WEBHOOK_HOST=os.getenv("WEBHOOK_HOST", "0.0.0.0"),
        WEBHOOK_PORT=int(os.getenv("PORT", os.getenv("WEBHOOK_PORT", "8000"))),
        PAYER_EMAIL_DOMAIN=os.getenv("PAYER_EMAIL_DOMAIN", "discord-subscriber.local"),
        ADMIN_KEY=os.getenv("ADMIN_KEY", ""),
        ADMIN_DISCORD_ID=os.getenv("ADMIN_DISCORD_ID", "1066862919960231986"),
    )