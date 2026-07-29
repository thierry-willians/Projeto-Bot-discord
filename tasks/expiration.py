"""Tarefas periódicas: remoção de cargo ao vencer e avisos de vencimento."""
import logging

from discord.ext import tasks

from bot.roles import remover_cargo
from config.settings import get_settings
from services import subscription

logger = logging.getLogger("tasks.expiration")


def setup_expiration_tasks(bot, db):
    settings = get_settings()

    @tasks.loop(hours=24)
    async def verificar_expirados():
        guild = bot.get_guild(settings.GUILD_ID)
        if guild is None:
            logger.warning("Guild indisponível ao checar expirados.")
            return

        # 1) Só lê do banco, libera o lock imediatamente.
        with db.connect() as conn:
            expirados = subscription.listar_expirados(conn)

        # 2) Chama o Discord SEM segurar o lock.
        for usuario in expirados:
            try:
                await remover_cargo(guild, usuario.discord_id, settings.ROLE_ID)
            except Exception as exc:  # noqa: BLE001
                logger.error("Erro ao remover cargo de %s: %s", usuario.discord_id, exc)

            # 3) Reabre o lock só pra escrever, rapidinho, por usuário.
            with db.connect() as conn:
                subscription.marcar_inativo(conn, usuario)
            logger.info("Assinatura de %s marcada como inativa.", usuario.discord_id)

    @tasks.loop(hours=24)
    async def avisar_vencimento():
        guild = bot.get_guild(settings.GUILD_ID)
        if guild is None:
            return

        # 1) Só lê do banco, libera o lock imediatamente.
        usuarios_por_dias = {}
        with db.connect() as conn:
            for dias in (7, 1):
                usuarios_por_dias[dias] = subscription.listar_a_vencer(conn, dias)

        # 2) Envia as DMs SEM segurar o lock.
        for dias, usuarios in usuarios_por_dias.items():
            plural = "dias" if dias > 1 else "dia"
            for usuario in usuarios:
                member = guild.get_member(int(usuario.discord_id))
                if member is None:
                    continue
                try:
                    await member.send(
                        f"Sua assinatura vence em {dias} {plural}. "
                        "Use /assinar no servidor para renovar e não perder o acesso."
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.error("Erro ao avisar %s: %s", usuario.discord_id, exc)

    return verificar_expirados, avisar_vencimento
