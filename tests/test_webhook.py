"""
Testes do webhook FastAPI. Precisam de `fastapi` e `httpx` instalados
(pip install -r requirements.txt) para rodar, já que usam TestClient.
"""
import pytest
from fastapi.testclient import TestClient

from api.webhook import build_webhook_app
from services.mercadopago import MercadoPagoError


class FakeMercadoPagoClient:
    """Substitui o cliente real: o teste controla o que a API 'retornaria'."""

    def __init__(self, respostas: dict):
        self.respostas = respostas  # payment_id -> dict (ou Exception)
        self.chamadas = []

    def consultar_pagamento(self, payment_id: str):
        self.chamadas.append(payment_id)
        resposta = self.respostas.get(payment_id)
        if isinstance(resposta, Exception):
            raise resposta
        if resposta is None:
            raise MercadoPagoError("payment not found")
        return resposta


class FakeGuild:
    def __init__(self, guild_id):
        self.id = guild_id


class FakeBot:
    def __init__(self, guild=None):
        self._guild = guild

    def get_guild(self, guild_id):
        return self._guild


@pytest.fixture
def client_factory(db, settings):
    """Retorna uma função que monta um TestClient com um mp_client fake dado."""

    def _make(respostas, guild=None):
        mp_client = FakeMercadoPagoClient(respostas)
        bot = FakeBot(guild=guild or FakeGuild(settings.GUILD_ID))
        app = build_webhook_app(bot, db, mp_client=mp_client)
        return TestClient(app), mp_client

    return _make


def test_webhook_sem_payment_id_e_ignorado(client_factory):
    client, _ = client_factory({})
    resp = client.post("/webhook/mercadopago", json={"type": "merchant_order"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "ignorado"


def test_webhook_pagamento_ainda_pendente(client_factory):
    client, _ = client_factory({"111": {"status": "pending", "external_reference": "999"}})
    resp = client.post("/webhook/mercadopago", json={"type": "payment", "data": {"id": "111"}})
    assert resp.status_code == 200
    assert resp.json()["status"] == "aguardando"


def test_webhook_pagamento_aprovado_libera_cargo(client_factory, monkeypatch, settings):
    chamadas_cargo = []

    async def fake_adicionar_cargo(guild, discord_id, role_id):
        chamadas_cargo.append((discord_id, role_id))

    monkeypatch.setattr("api.webhook.adicionar_cargo", fake_adicionar_cargo)

    client, mp_client = client_factory(
        {"222": {"status": "approved", "external_reference": "999", "transaction_amount": 100.0}}
    )
    resp = client.post("/webhook/mercadopago", json={"type": "payment", "data": {"id": "222"}})

    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    assert chamadas_cargo == [("999", settings.ROLE_ID)]

    # O status é sempre verificado direto na API do Mercado Pago, nunca só
    # confiando no corpo do webhook.
    assert mp_client.chamadas == ["222"]


def test_webhook_duplicado_nao_adiciona_cargo_duas_vezes(client_factory, monkeypatch):
    chamadas_cargo = []

    async def fake_adicionar_cargo(guild, discord_id, role_id):
        chamadas_cargo.append((discord_id, role_id))

    monkeypatch.setattr("api.webhook.adicionar_cargo", fake_adicionar_cargo)

    client, _ = client_factory(
        {"333": {"status": "approved", "external_reference": "999", "transaction_amount": 100.0}}
    )

    resp1 = client.post("/webhook/mercadopago", json={"type": "payment", "data": {"id": "333"}})
    resp2 = client.post("/webhook/mercadopago", json={"type": "payment", "data": {"id": "333"}})

    assert resp1.json()["status"] == "ok"
    assert resp2.json()["status"] == "ja_processado"
    assert len(chamadas_cargo) == 1  # cargo só foi adicionado uma vez


def test_webhook_valor_abaixo_do_esperado_nao_libera_cargo(client_factory, monkeypatch):
    chamadas_cargo = []

    async def fake_adicionar_cargo(guild, discord_id, role_id):
        chamadas_cargo.append((discord_id, role_id))

    monkeypatch.setattr("api.webhook.adicionar_cargo", fake_adicionar_cargo)

    client, _ = client_factory(
        {"444": {"status": "approved", "external_reference": "999", "transaction_amount": 1.0}}
    )
    resp = client.post("/webhook/mercadopago", json={"type": "payment", "data": {"id": "444"}})

    assert resp.json()["status"] == "valor_invalido"
    assert chamadas_cargo == []


def test_webhook_erro_ao_consultar_mercadopago_retorna_502(client_factory):
    client, _ = client_factory({"555": MercadoPagoError("timeout")})
    resp = client.post("/webhook/mercadopago", json={"type": "payment", "data": {"id": "555"}})
    assert resp.status_code == 502
