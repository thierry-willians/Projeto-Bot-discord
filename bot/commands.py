import uuid
import asyncio
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
        qr_code = (
            pagamento_mp.get("point_of_interaction", {})
            .get("transaction_data", {})
            .get("qr_code")
        )

        with db.connect() as conn:
            subscription.registrar_pagamento_pendente(
                conn, payment_id, discord_id, settings.SUBSCRIPTION_PRICE
            )

        if qr_code:
            texto = (
                f"**Assinatura — R$ {settings.SUBSCRIPTION_PRICE:.2f}/mês**\n\n"
                "Copie o código Pix abaixo e pague no app do seu banco. "
                "Seu acesso é liberado automaticamente em poucos segundos após a confirmação.\n\n"
                f"```{qr_code}```"
            )
        else:
            texto = (
                "PIX gerado, mas não recebi o código copia-e-cola do Mercado Pago. "
                "Contate o suporte informando o código de referência: "
                f"`{payment_id}`."
            )

        await interaction.followup.send(texto, ephemeral=True)
