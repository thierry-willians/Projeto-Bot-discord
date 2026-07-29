"""
Testes da camada de repositório (sqlite3 puro).

Usa unittest da biblioteca padrão de propósito: roda com
`python3 -m unittest` sem precisar instalar nada, e também é coletado
normalmente pelo pytest quando as demais dependências estiverem instaladas.
"""
import unittest
from datetime import datetime, timedelta

from database import repository
from database.connection import Database
from database.models import Pagamento, Usuario


class TestRepository(unittest.TestCase):
    def setUp(self):
        self.db = Database(":memory:")

    def tearDown(self):
        self.db.close()

    def test_upsert_e_get_usuario(self):
        with self.db.connect() as conn:
            repository.upsert_usuario(conn, Usuario(discord_id="1", nome="Ana", status="ativo"))
            usuario = repository.get_usuario(conn, "1")

        self.assertIsNotNone(usuario)
        self.assertEqual(usuario.nome, "Ana")
        self.assertEqual(usuario.status, "ativo")

    def test_upsert_usuario_atualiza_registro_existente(self):
        with self.db.connect() as conn:
            repository.upsert_usuario(conn, Usuario(discord_id="1", status="inativo"))
            repository.upsert_usuario(conn, Usuario(discord_id="1", status="ativo"))
            usuario = repository.get_usuario(conn, "1")

        self.assertEqual(usuario.status, "ativo")

    def test_get_usuario_inexistente_retorna_none(self):
        with self.db.connect() as conn:
            usuario = repository.get_usuario(conn, "nao-existe")
        self.assertIsNone(usuario)

    def test_upsert_e_get_pagamento(self):
        with self.db.connect() as conn:
            repository.upsert_usuario(conn, Usuario(discord_id="1"))
            repository.upsert_pagamento(
                conn, Pagamento(payment_id="p1", discord_id="1", valor=100.0, status="pending")
            )
            pagamento = repository.get_pagamento(conn, "p1")

        self.assertIsNotNone(pagamento)
        self.assertEqual(pagamento.valor, 100.0)
        self.assertFalse(pagamento.processado)

    def test_listar_usuarios_expirados(self):
        with self.db.connect() as conn:
            repository.upsert_usuario(
                conn,
                Usuario(
                    discord_id="expirado",
                    status="ativo",
                    data_expiracao=datetime.utcnow() - timedelta(days=1),
                ),
            )
            repository.upsert_usuario(
                conn,
                Usuario(
                    discord_id="valido",
                    status="ativo",
                    data_expiracao=datetime.utcnow() + timedelta(days=10),
                ),
            )
            expirados = repository.listar_usuarios_expirados(conn, datetime.utcnow())

        ids = [u.discord_id for u in expirados]
        self.assertIn("expirado", ids)
        self.assertNotIn("valido", ids)

    def test_listar_usuarios_a_vencer(self):
        agora = datetime.utcnow()
        with self.db.connect() as conn:
            repository.upsert_usuario(
                conn,
                Usuario(discord_id="vence_em_7", status="ativo", data_expiracao=agora + timedelta(days=7)),
            )
            repository.upsert_usuario(
                conn,
                Usuario(discord_id="vence_em_20", status="ativo", data_expiracao=agora + timedelta(days=20)),
            )
            janela_inicio = (agora + timedelta(days=7)).replace(hour=0, minute=0, second=0, microsecond=0)
            janela_fim = janela_inicio + timedelta(days=1)
            a_vencer = repository.listar_usuarios_a_vencer(conn, janela_inicio, janela_fim)

        ids = [u.discord_id for u in a_vencer]
        self.assertIn("vence_em_7", ids)
        self.assertNotIn("vence_em_20", ids)


if __name__ == "__main__":
    unittest.main()
