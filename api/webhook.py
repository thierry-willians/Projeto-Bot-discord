"""
Webhook do Mercado Pago.

Regra de segurança mais importante deste arquivo: NUNCA confiar no corpo do
webhook para liberar acesso. O webhook só é usado como um "sinal" de que algo
mudou; o status real do pagamento é sempre confirmado consultando a API do
Mercado Pago (mp_client.consultar_pagamento).
"""
import logging
from datetime import datetime, timedelta

from fastapi import FastAPI, HTTPException, Request

from bot.roles import adicionar_cargo, remover_cargo
from config.settings import get_settings
from database import repository
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

    # ------------------------------------------------------------------
    # ROTAS TEMPORÁRIAS DE TESTE — remover antes de divulgar o bot.
    # Só existem se ADMIN_KEY estiver configurada no .env / Railway.
    # ------------------------------------------------------------------
    if settings.ADMIN_KEY:

        def _checar_chave(chave: str) -> None:
            if chave != settings.ADMIN_KEY:
                raise HTTPException(status_code=403, detail="Chave inválida")

        @app.get("/admin/status")
        async def admin_status(chave: str, discord_id: str):
            _checar_chave(chave)
            with db.connect() as conn:
                usuario = repository.get_usuario(conn, discord_id)
            if usuario is None:
                return {"encontrado": False}
            return {
                "encontrado": True,
                "discord_id": usuario.discord_id,
                "status": usuario.status,
                "data_inicio": usuario.data_inicio.isoformat() if usuario.data_inicio else None,
                "data_expiracao": usuario.data_expiracao.isoformat()
                if usuario.data_expiracao
                else None,
            }

        @app.get("/admin/set-expiracao")
        async def admin_set_expiracao(chave: str, discord_id: str, dias: int):
            """dias pode ser negativo (já venceu) ou positivo (vence no futuro)."""
            _checar_chave(chave)
            with db.connect() as conn:
                usuario = repository.get_usuario(conn, discord_id)
                if usuario is None:
                    raise HTTPException(
                        status_code=404,
                        detail="Usuário não encontrado. Rode /assinar pelo menos uma vez antes.",
                    )
                usuario.data_expiracao = datetime.utcnow() + timedelta(days=dias)
                usuario.status = "ativo"
                repository.upsert_usuario(conn, usuario)
            return {"status": "ok", "nova_data_expiracao": usuario.data_expiracao.isoformat()}

        @app.post("/admin/rodar-expiracao")
        async def admin_rodar_expiracao(chave: str):
            _checar_chave(chave)
            guild = bot.get_guild(settings.GUILD_ID)
            if guild is None:
                raise HTTPException(status_code=503, detail="Guild indisponível")

            # 1) Só lê do banco, libera o lock imediatamente.
            with db.connect() as conn:
                expirados = subscription.listar_expirados(conn)

            # 2) Chama o Discord SEM segurar o lock.
            resultados = []
            for usuario in expirados:
                try:
                    await remover_cargo(guild, usuario.discord_id, settings.ROLE_ID)
                    resultados.append({"discord_id": usuario.discord_id, "cargo_removido": True})
                except Exception as exc:  # noqa: BLE001
                    resultados.append({"discord_id": usuario.discord_id, "erro": str(exc)})

                # 3) Reabre o lock só pra escrever, rapidinho, por usuário.
                with db.connect() as conn:
                    subscription.marcar_inativo(conn, usuario)

            return {"processados": resultados}

        @app.post("/admin/rodar-avisos")
        async def admin_rodar_avisos(chave: str):
            _checar_chave(chave)
            guild = bot.get_guild(settings.GUILD_ID)
            if guild is None:
                raise HTTPException(status_code=503, detail="Guild indisponível")

            # 1) Só lê do banco, libera o lock imediatamente.
            usuarios_por_dias: dict[int, list] = {}
            with db.connect() as conn:
                for dias in (7, 1):
                    usuarios_por_dias[dias] = subscription.listar_a_vencer(conn, dias)

            # 2) Envia as DMs SEM segurar o lock.
            enviados = []
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
                        enviados.append({"discord_id": usuario.discord_id, "dias": dias})
                    except Exception as exc:  # noqa: BLE001
                        enviados.append({"discord_id": usuario.discord_id, "erro": str(exc)})

            return {"enviados": enviados}

    return app
