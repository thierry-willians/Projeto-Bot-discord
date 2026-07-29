import httpx
import pytest

from services.mercadopago import MercadoPagoClient, MercadoPagoError


class FakeResponse:
    def __init__(self, status_code, json_data):
        self.status_code = status_code
        self._json = json_data
        self.text = str(json_data)

    def json(self):
        return self._json


def test_criar_pagamento_pix_sucesso(monkeypatch):
    def fake_post(self, url, json=None, headers=None):
        assert url.endswith("/v1/payments")
        assert json["external_reference"] == "999"
        assert json["payment_method_id"] == "pix"
        assert headers["Authorization"] == "Bearer fake-token"
        return FakeResponse(201, {"id": 12345, "status": "pending"})

    monkeypatch.setattr(httpx.Client, "post", fake_post)

    client = MercadoPagoClient("fake-token")
    resultado = client.criar_pagamento_pix(
        valor=100.0,
        discord_id="999",
        descricao="teste",
        payer_email="999@example.com",
    )
    assert resultado["id"] == 12345


def test_criar_pagamento_pix_erro_levanta_excecao(monkeypatch):
    def fake_post(self, url, json=None, headers=None):
        return FakeResponse(400, {"message": "invalid payer email"})

    monkeypatch.setattr(httpx.Client, "post", fake_post)

    client = MercadoPagoClient("fake-token")
    with pytest.raises(MercadoPagoError):
        client.criar_pagamento_pix(
            valor=100.0, discord_id="999", descricao="teste", payer_email="invalido"
        )


def test_consultar_pagamento_sucesso(monkeypatch):
    def fake_get(self, url, headers=None):
        assert url.endswith("/v1/payments/12345")
        return FakeResponse(200, {"id": 12345, "status": "approved", "external_reference": "999"})

    monkeypatch.setattr(httpx.Client, "get", fake_get)

    client = MercadoPagoClient("fake-token")
    resultado = client.consultar_pagamento("12345")
    assert resultado["status"] == "approved"
    assert resultado["external_reference"] == "999"


def test_consultar_pagamento_erro_levanta_excecao(monkeypatch):
    def fake_get(self, url, headers=None):
        return FakeResponse(404, {"message": "not found"})

    monkeypatch.setattr(httpx.Client, "get", fake_get)

    client = MercadoPagoClient("fake-token")
    with pytest.raises(MercadoPagoError):
        client.consultar_pagamento("does-not-exist")
