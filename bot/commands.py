import uuid
import asyncio
import base64
import io
import discord

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
