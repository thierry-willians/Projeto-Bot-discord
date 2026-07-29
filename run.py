import asyncio
import logging

import uvicorn

from api.webhook import build_webhook_app
from bot.main import build_bot
from config.settings import get_settings
from tasks.expiration import setup_expiration_tasks

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


async def main() -> None:
    settings = get_settings()

    bot = build_bot()
    app = build_webhook_app(bot, bot.db)
    verificar_expirados, avisar_vencimento = setup_expiration_tasks(bot, bot.db)

    @bot.event
    async def on_connect():
        if not verificar_expirados.is_running():
            verificar_expirados.start()
        if not avisar_vencimento.is_running():
            avisar_vencimento.start()

    config = uvicorn.Config(
        app,
        host=settings.WEBHOOK_HOST,
        port=settings.WEBHOOK_PORT,
        log_level="info",
    )
    server = uvicorn.Server(config)

    await asyncio.gather(
        bot.start(settings.DISCORD_TOKEN),
        server.serve(),
    )


if __name__ == "__main__":
    asyncio.run(main())
