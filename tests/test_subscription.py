"""
Testes das regras de negócio de assinatura: ativação, idempotência de
webhook duplicado, validação de valor, renovação antecipada e expiração.

Roda com `python3 -m unittest` (só biblioteca padrão) e também com pytest.
"""
import unittest
from datetime import datetime, timedelta

from database import repository
from database.connection import Database
from services import subscription


class TestSubscription(unittest.TestCase):
    def setUp(self):
        self.db = Database(":memory:")

    def tearDown(self):
        self.db.close()

    def test_registrar_pagamento_pendente_cria_usuario_e_pagamento(self):
        with self.db.connect() as conn:
            pagamento = subscription.registrar_pagamento_pendente(conn, "pay-1", "999", 100.0)
            usuario = repository.get_usuario(conn, "999")

        self.assertEqual(pagamento.status, "pending")
        self.assertIsNotNone(usuario)
        self.assertEqual(usuario.status, "inativo")

    def test_processar_pagamento_aprovado_ativa_usuario_por_30_dias(self):
        with self.db.connect() as conn:
            pagamento, processado_agora = subscription.processar_pagamento_aprovado(
                conn, "pay-2", "999", 100.0, dias=30, valor_esperado=100.0
            )
            usuario = repository.get_usuario(conn, "999")

        self.assertTrue(processado_agora)
        self.assertEqual(pagamento.status, "approved")
        self.assertEqual(usuario.status, "ativo")
        self.assertIsNotNone(usuario.data_expiracao)
        dias_restantes = (usuario.data_expiracao - datetime.utcnow()).days
        self.assertTrue(28 <= dias_restantes <= 30, f"dias_restantes={dias_restantes}")

    def test_webhook_duplicado_e_idempotente(self):
        with self.db.connect() as conn:
            subscription.processar_pagamento_aprovado(conn, "pay-3", "999", 100.0, valor_esperado=100.0)
            usuario_antes = repository.get_usuario(conn, "999")
            expiracao_original = usuario_antes.data_expiracao

            # Mesmo payment_id chega de novo (webhook duplicado do Mercado Pago)
            _, processado_agora = subscription.processar_pagamento_aprovado(
                conn, "pay-3", "999", 100.0, valor_esperado=100.0
            )
            usuario_depois = repository.get_usuario(conn, "999")

        self.assertFalse(processado_agora)
        self.assertEqual(usuario_depois.data_expiracao, expiracao_original)  # não duplicou

    def test_valor_abaixo_do_esperado_e_rejeitado(self):
        with self.db.connect() as conn:
            with self.assertRaises(ValueError):
                subscription.processar_pagamento_aprovado(
                    conn, "pay-4", "999", 50.0, valor_esperado=100.0
                )
            usuario = repository.get_usuario(conn, "999")

        self.assertIsNone(usuario)  # nunca chegou a ativar

    def test_renovacao_antecipada_soma_dias_ao_vencimento_atual(self):
        with self.db.connect() as conn:
            subscription.processar_pagamento_aprovado(conn, "pay-5", "999", 100.0, dias=30, valor_esperado=100.0)
            expiracao_1 = repository.get_usuario(conn, "999").data_expiracao

            # Renova antes de vencer
            subscription.processar_pagamento_aprovado(conn, "pay-6", "999", 100.0, dias=30, valor_esperado=100.0)
            expiracao_2 = repository.get_usuario(conn, "999").data_expiracao

        # A segunda expiração deve ser ~30 dias DEPOIS da primeira, não a partir de "agora".
        diferenca = expiracao_2 - expiracao_1
        self.assertTrue(29 <= diferenca.days <= 30, f"diferenca.days={diferenca.days}")

    def test_listar_expirados(self):
        with self.db.connect() as conn:
            repository.upsert_usuario(
                conn,
                repository.Usuario(
                    discord_id="777",
                    status="ativo",
                    data_inicio=datetime.utcnow() - timedelta(days=40),
                    data_expiracao=datetime.utcnow() - timedelta(days=10),
                ),
            )
            expirados = subscription.listar_expirados(conn)

        self.assertEqual(len(expirados), 1)
        self.assertEqual(expirados[0].discord_id, "777")

    def test_listar_a_vencer_em_7_dias(self):
        with self.db.connect() as conn:
            repository.upsert_usuario(
                conn,
                repository.Usuario(
                    discord_id="888",
                    status="ativo",
                    data_inicio=datetime.utcnow(),
                    data_expiracao=datetime.utcnow() + timedelta(days=7),
                ),
            )
            a_vencer = subscription.listar_a_vencer(conn, dias=7)

        self.assertEqual(len(a_vencer), 1)
        self.assertEqual(a_vencer[0].discord_id, "888")

    def test_marcar_inativo(self):
        with self.db.connect() as conn:
            usuario = repository.Usuario(discord_id="555", status="ativo")
            repository.upsert_usuario(conn, usuario)
            subscription.marcar_inativo(conn, usuario)
            usuario_final = repository.get_usuario(conn, "555")

        self.assertEqual(usuario_final.status, "inativo")


if __name__ == "__main__":
    unittest.main()
