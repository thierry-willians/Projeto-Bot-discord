"""
Regras de negócio da assinatura: criação, aprovação (idempotente), expiração
e avisos de vencimento. Depende só de database/repository.py, o que torna
essas funções fáceis de testar com um banco SQLite temporário, sem precisar
de Discord, FastAPI ou rede.
"""
import sqlite3
from datetime import datetime, timedelta

from database import repository
from database.models import Pagamento, Usuario


def registrar_pagamento_pendente(
    conn: sqlite3.Connection, payment_id: str, discord_id: str, valor: float
) -> Pagamento:
    """Registra um pagamento pendente assim que o PIX é gerado (comando /assinar)."""
    usuario = repository.get_usuario(conn, discord_id)
    if usuario is None:
        usuario = Usuario(discord_id=discord_id, status="inativo")
        repository.upsert_usuario(conn, usuario)

    pagamento = repository.get_pagamento(conn, payment_id)
    if pagamento is None:
        pagamento = Pagamento(
            payment_id=payment_id,
            discord_id=discord_id,
            valor=valor,
            status="pending",
            data_pagamento=datetime.utcnow(),
        )
        repository.upsert_pagamento(conn, pagamento)

    return pagamento


def processar_pagamento_aprovado(
    conn: sqlite3.Connection,
    payment_id: str,
    discord_id: str,
    valor: float,
    dias: int = 30,
    valor_esperado: float = 100.0,
) -> tuple[Pagamento, bool]:
    """
    Aplica um pagamento aprovado (já validado contra a API do Mercado Pago
    pelo chamador). Idempotente: se o payment_id já foi processado, não
    duplica a assinatura.

    Retorna (pagamento, processado_agora). `processado_agora` é False quando
    o pagamento já havia sido processado antes (webhook duplicado).
    """
    pagamento = repository.get_pagamento(conn, payment_id)
    if pagamento is None:
        pagamento = Pagamento(
            payment_id=payment_id,
            discord_id=discord_id,
            valor=valor,
            status="pending",
            data_pagamento=datetime.utcnow(),
        )

    if pagamento.processado:
        return pagamento, False

    if round(float(valor), 2) < round(float(valor_esperado), 2):
        pagamento.status = "valor_invalido"
        repository.upsert_pagamento(conn, pagamento)
        raise ValueError(
            f"Valor do pagamento ({valor}) é menor que o esperado ({valor_esperado})"
        )

    usuario = repository.get_usuario(conn, discord_id)
    if usuario is None:
        usuario = Usuario(discord_id=discord_id)

    agora = datetime.utcnow()
    # Se o usuário renovar antes de vencer, a nova validade soma a partir do
    # vencimento atual (não perde os dias restantes). Se já venceu (ou é a
    # primeira assinatura), conta a partir de agora.
    inicio_contagem = agora
    if usuario.data_expiracao and usuario.data_expiracao > agora:
        inicio_contagem = usuario.data_expiracao

    usuario.data_inicio = usuario.data_inicio or agora
    usuario.data_expiracao = inicio_contagem + timedelta(days=dias)
    usuario.status = "ativo"
    repository.upsert_usuario(conn, usuario)

    pagamento.status = "approved"
    pagamento.processado = True
    pagamento.valor = valor
    repository.upsert_pagamento(conn, pagamento)

    return pagamento, True


def listar_expirados(conn: sqlite3.Connection, agora: datetime | None = None) -> list[Usuario]:
    """Usuários ativos cuja assinatura já venceu (para remoção de cargo)."""
    agora = agora or datetime.utcnow()
    return repository.listar_usuarios_expirados(conn, agora)


def listar_a_vencer(
    conn: sqlite3.Connection, dias: int, agora: datetime | None = None
) -> list[Usuario]:
    """Usuários ativos cuja assinatura vence daqui a `dias` dias (janela de 1 dia)."""
    agora = agora or datetime.utcnow()
    alvo = agora + timedelta(days=dias)
    janela_inicio = alvo.replace(hour=0, minute=0, second=0, microsecond=0)
    janela_fim = janela_inicio + timedelta(days=1)
    return repository.listar_usuarios_a_vencer(conn, janela_inicio, janela_fim)


def marcar_inativo(conn: sqlite3.Connection, usuario: Usuario) -> None:
    usuario.status = "inativo"
    repository.upsert_usuario(conn, usuario)
