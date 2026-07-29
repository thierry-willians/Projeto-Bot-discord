from services.mercadopago import MercadoPagoClient, MercadoPagoError
from config.settings import get_settings
import uuid

settings = get_settings()
client = MercadoPagoClient(settings.MP_ACCESS_TOKEN)

try:
    resultado = client.criar_pagamento_pix(
    valor=100.0,
    discord_id="123456789",
    descricao="teste",
    payer_email="teste123456789@gmail.com",
    idempotency_key=str(uuid.uuid4()),
    )
    print("SUCESSO:", resultado)
except MercadoPagoError as e:
    print("ERRO:", e)