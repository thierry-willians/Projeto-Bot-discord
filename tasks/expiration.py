"""Task periódica: posta no Discord o relatório semanal mais recente
que o bot local enviou e que ainda não foi postado.

Roda a cada 5 min. Posta só quando:
  - é o dia configurado (REPORT_WEEKDAY, padrão segunda) em BRT
  - a hora BRT >= REPORT_HOUR (padrão 7)
  - existe relatório com postado=false
"""
import io
import logging
from datetime import datetime, timezone, timedelta

import discord
from discord.ext import tasks

from config.settings import get_settings
from database import repository

logger = logging.getLogger("tasks.relatorio")

BRT = timezone(timedelta(hours=-3))


def setup_relatorio_tasks(bot, db):
    settings = get_settings()

    @tasks.loop(minutes=5)
    async def postar_relatorio_semanal():
        agora_brt = datetime.now(BRT)

        if agora_brt.weekday() != settings.REPORT_WEEKDAY:
            return
        if agora_brt.hour < settings.REPORT_HOUR:
            return

        with db.connect() as conn:
            pendentes = repository.listar_relatorios_pendentes(conn)

        if not pendentes:
            return

        canal = bot.get_channel(settings.REPORT_CHANNEL_ID)
        if canal is None:
            logger.error(
                "Canal de relatório %s indisponível.",
                settings.REPORT_CHANNEL_ID,
            )
            return

        for rel in pendentes:
            try:
                arquivo = discord.File(
                    io.BytesIO(rel.png_blob),
                    filename=f"relatorio_{rel.semana_inicio}.png",
                )
                embed = discord.Embed(
                    title="Relatório Semanal",
                    description=(
                        f"Período: **{rel.semana_inicio}** a **{rel.semana_fim}**\n"
                        f"IDs processados: **{rel.total_ids}**\n"
                        f"Ofertas enviadas: **{rel.total_ofertas}**\n"
                        f"Tempo de sessão: **{rel.tempo_total_horas:.1f}h**"
                    ),
                    color=discord.Color.blue(),
                )
                embed.set_image(url=f"attachment://relatorio_{rel.semana_inicio}.png")
                msg = await canal.send(embed=embed, file=arquivo)
                with db.connect() as conn:
                    repository.marcar_relatorio_postado(conn, rel.id, msg.id)
                logger.info(
                    "Relatório semanal %s postado no Discord (msg=%s).",
                    rel.semana_inicio, msg.id,
                )
            except Exception as exc:
                logger.error("Falha ao postar relatório %s: %s", rel.id, exc)

    return postar_relatorio_semanal
