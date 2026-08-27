import uuid
import asyncio
import base64
import io
from datetime import datetime

import discord

from database import repository
from config.settings import get_settings
from services import subscription
from services.mercadopago import MercadoPagoClient, MercadoPagoError


def setup_commands(bot: discord.Client, db, mp_client: MercadoPagoClient | None = None) -> None:
    settings = get_settings()
    mp_client = mp_client or MercadoPagoClient(settings.MP_ACCESS_TOKEN)

    @bot.tree.command(
        name="assinar",
        description="Gera um PIX para assinar o acesso ao servidor de ofertas (R$ %.2f/mês)"
        % settings.SUBSCRIPTION_PRICE,
    )
    async def assinar(interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)

        discord_id = str(interaction.user.id)
        payer_email = f"{discord_id}@{settings.PAYER_EMAIL_DOMAIN}"

        try:
            pagamento_mp = await asyncio.to_thread(
                mp_client.criar_pagamento_pix,
                valor=settings.SUBSCRIPTION_PRICE,
                discord_id=discord_id,
                descricao="Assinatura mensal - Servidor de Ofertas",
                payer_email=payer_email,
                idempotency_key=str(uuid.uuid4()),
            )
        except MercadoPagoError:
            await interaction.followup.send(
                "Não consegui gerar o pagamento agora. Tente novamente em instantes "
                "ou contate o suporte se o problema persistir.",
                ephemeral=True,
            )
            return

        payment_id = str(pagamento_mp["id"])
        transaction_data = pagamento_mp.get("point_of_interaction", {}).get(
            "transaction_data", {}
        )
        qr_code = transaction_data.get("qr_code")
        qr_code_base64 = transaction_data.get("qr_code_base64")

        with db.connect() as conn:
            subscription.registrar_pagamento_pendente(
                conn, payment_id, discord_id, settings.SUBSCRIPTION_PRICE
            )

        if not qr_code and not qr_code_base64:
            await interaction.followup.send(
                "PIX gerado, mas não recebi o código do Mercado Pago. "
                "Contate o suporte informando o código de referência: "
                f"`{payment_id}`.",
                ephemeral=True,
            )
            return

        texto = (
            f"**Assinatura — R$ {settings.SUBSCRIPTION_PRICE:.2f}/mês**\n\n"
            "Escaneie o QR Code abaixo pelo app do seu banco ou copie o código Pix. "
            "Seu acesso é liberado automaticamente em poucos segundos após a confirmação."
        )
        if qr_code:
            texto += f"\n\n**Código Pix (copia e cola):**\n```{qr_code}```"

        arquivo = None
        embed = None
        if qr_code_base64:
            try:
                imagem_bytes = base64.b64decode(qr_code_base64)
                arquivo = discord.File(io.BytesIO(imagem_bytes), filename="pix.png")
                embed = discord.Embed(color=discord.Color.green())
                embed.set_image(url="attachment://pix.png")
            except (ValueError, TypeError):
                arquivo = None
                embed = None

        await interaction.followup.send(
            texto,
            embed=embed,
            file=arquivo,
            ephemeral=True,
        )

    @bot.tree.command(
        name="status",
        description="Veja quantos dias restam na sua assinatura.",
    )
    async def status(interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)

        discord_id = str(interaction.user.id)

        with db.connect() as conn:
            usuario = repository.get_usuario(conn, discord_id)

        if usuario is None or usuario.status != "ativo" or usuario.data_expiracao is None:
            await interaction.followup.send(
                "Você não tem uma assinatura ativa no momento. "
                "Use `/assinar` para gerar um PIX e liberar seu acesso.",
                ephemeral=True,
            )
            return

        agora = datetime.utcnow()
        restante = usuario.data_expiracao - agora

        if restante.total_seconds() <= 0:
            await interaction.followup.send(
                "Sua assinatura venceu. Use `/assinar` para renovar.",
                ephemeral=True,
            )
            return

        dias_restantes = restante.days
        horas_restantes = restante.seconds // 3600
        data_formatada = usuario.data_expiracao.strftime("%d/%m/%Y às %H:%M")

        if dias_restantes >= 1:
            tempo_texto = f"**{dias_restantes} dia(s)** e {horas_restantes}h"
        else:
            tempo_texto = f"**{horas_restantes}h**"

        embed = discord.Embed(
            title="Status da assinatura",
            color=discord.Color.green(),
        )
        embed.add_field(name="Status", value="Ativa", inline=True)
        embed.add_field(name="Tempo restante", value=tempo_texto, inline=True)
        embed.add_field(name="Expira em", value=data_formatada, inline=False)

        await interaction.followup.send(embed=embed, ephemeral=True)
