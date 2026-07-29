"""
Webhook do Mercado Pago.

Regra de segurança mais importante deste arquivo: NUNCA confiar no corpo do
webhook para liberar acesso. O webhook só é usado como um "sinal" de que algo
mudou; o status real do pagamento é sempre confirmado consultando a API do
Mercado Pago (mp_client.consultar_pagamento).
"""
import logging

from fastapi import FastAPI, HTTPException, Request

from bot.roles import adicionar_cargo
from config.settings import get_settings
from services import subscription
from services.mercadopago import MercadoPagoClient, MercadoPagoError

logger = logging.getLogger("webhook")


def build_webhook_app(bot, db, mp_client: MercadoPagoClient | None = None) -> FastAPI:
    settings = get_settings()
    mp_client = mp_client or MercadoPagoClient(settings.MP_ACCESS_TOKEN)

    app = FastAPI(title="Webhook - Assinaturas Discord")

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.post("/webhook/mercadopago")
    async def mercadopago_webhook(request: Request):
        try:
            body = await request.json()
        except Exception:
            body = {}

        payment_id = None
        if isinstance(body, dict) and body.get("type") == "payment":
            payment_id = body.get("data", {}).get("id")

        # O Mercado Pago também pode notificar via query string.
        payment_id = (
            payment_id
            or request.query_params.get("id")
            or request.query_params.get("data.id")
        )

        if not payment_id:
            # Notificação irrelevante (ex: teste, merchant_order). Responder
            # 200 para o Mercado Pago não ficar reenviando.
            return {"status": "ignorado"}

        try:
            pagamento_mp = mp_client.consultar_pagamento(str(payment_id))
        except MercadoPagoError as exc:
            logger.error("Falha ao consultar pagamento %s: %s", payment_id, exc)
            raise HTTPException(status_code=502, detail="Falha ao consultar Mercado Pago")

        if pagamento_mp.get("status") != "approved":
            return {"status": "aguardando", "mp_status": pagamento_mp.get("status")}

        discord_id = pagamento_mp.get("external_reference")
        if not discord_id:
            logger.warning("Pagamento %s aprovado sem external_reference.", payment_id)
            return {"status": "sem_referencia"}

        valor = float(pagamento_mp.get("transaction_amount", 0))

        with db.connect() as conn:
            try:
                _, processado_agora = subscription.processar_pagamento_aprovado(
                    conn,
                    str(payment_id),
                    str(discord_id),
                    valor,
                    dias=settings.SUBSCRIPTION_DAYS,
                    valor_esperado=settings.SUBSCRIPTION_PRICE,
                )
            except ValueError:
                logger.warning(
                    "Pagamento %s com valor abaixo do esperado (recebido=%s).",
                    payment_id,
                    valor,
                )
                return {"status": "valor_invalido"}

        if not processado_agora:
            # Webhook duplicado — já processamos esse payment_id antes.
            return {"status": "ja_processado"}

        guild = bot.get_guild(settings.GUILD_ID)
        if guild is None:
            logger.error("Guild %s não encontrada pelo bot (ainda conectando?).", settings.GUILD_ID)
            return {"status": "aprovado_mas_guild_indisponivel"}

        try:
            await adicionar_cargo(guild, str(discord_id), settings.ROLE_ID)
        except Exception as exc:  # noqa: BLE001 - queremos logar qualquer falha aqui
            logger.error("Erro ao adicionar cargo para %s: %s", discord_id, exc)
            return {"status": "aprovado_mas_erro_ao_liberar_cargo"}

        return {"status": "ok"}

    return app
