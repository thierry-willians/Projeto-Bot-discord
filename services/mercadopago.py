import httpx
import uuid

MP_API_BASE = "https://api.mercadopago.com"


class MercadoPagoError(Exception):

class MercadoPagoClient:
    def __init__(self, access_token: str, timeout: float = 15.0):
        self.access_token = access_token
        self.timeout = timeout

    def _headers(self, idempotency_key: str | None = None) -> dict:
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
        if idempotency_key:
            headers["X-Idempotency-Key"] = idempotency_key
        return headers

    def criar_pagamento_pix(
        self,
        valor: float,
        discord_id: str,
        descricao: str,
        payer_email: str,
        idempotency_key: str | None = None,
    ) -> dict:
        idempotency_key = idempotency_key or str(uuid.uuid4())
        payload = {
            "transaction_amount": round(float(valor), 2),
            "description": descricao,
            "payment_method_id": "pix",
            "payer": {"email": payer_email},
            "external_reference": str(discord_id),
        }
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(
                f"{MP_API_BASE}/v1/payments",
                json=payload,
                headers=self._headers(idempotency_key),
            )
        if resp.status_code >= 400:
            raise MercadoPagoError(
                f"Erro ao criar pagamento ({resp.status_code}): {resp.text}"
            )
        return resp.json()

    def consultar_pagamento(self, payment_id: str) -> dict:
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.get(
                f"{MP_API_BASE}/v1/payments/{payment_id}",
                headers=self._headers(),
            )
        if resp.status_code >= 400:
            raise MercadoPagoError(
                f"Erro ao consultar pagamento ({resp.status_code}): {resp.text}"
            )
        return resp.json()
