"""
Camada de acesso a dados (SQL puro via sqlite3). Toda a lógica de negócio
fica em services/subscription.py; este módulo só sabe ler e gravar linhas.
"""
import sqlite3
from datetime import datetime
from typing import Optional

from database.models import Pagamento, Usuario

DATE_FMT = "%Y-%m-%dT%H:%M:%S.%f"


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    return datetime.strptime(value, DATE_FMT) if value else None


def _fmt_dt(value: Optional[datetime]) -> Optional[str]:
    return value.strftime(DATE_FMT) if value else None


def _row_to_usuario(row: sqlite3.Row) -> Usuario:
    return Usuario(
        discord_id=row["discord_id"],
        nome=row["nome"],
        data_inicio=_parse_dt(row["data_inicio"]),
        data_expiracao=_parse_dt(row["data_expiracao"]),
        status=row["status"],
    )


def _row_to_pagamento(row: sqlite3.Row) -> Pagamento:
    return Pagamento(
        payment_id=row["payment_id"],
        discord_id=row["discord_id"],
        valor=row["valor"],
        status=row["status"],
        data_pagamento=_parse_dt(row["data_pagamento"]),
        processado=bool(row["processado"]),
    )


def get_usuario(conn: sqlite3.Connection, discord_id: str) -> Optional[Usuario]:
    row = conn.execute(
        "SELECT * FROM usuarios WHERE discord_id = ?", (discord_id,)
    ).fetchone()
    return _row_to_usuario(row) if row else None


def upsert_usuario(conn: sqlite3.Connection, usuario: Usuario) -> None:
    conn.execute(
        """
        INSERT INTO usuarios (discord_id, nome, data_inicio, data_expiracao, status)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(discord_id) DO UPDATE SET
            nome = excluded.nome,
            data_inicio = excluded.data_inicio,
            data_expiracao = excluded.data_expiracao,
            status = excluded.status
        """,
        (
            usuario.discord_id,
            usuario.nome,
            _fmt_dt(usuario.data_inicio),
            _fmt_dt(usuario.data_expiracao),
            usuario.status,
        ),
    )
    conn.commit()


def get_pagamento(conn: sqlite3.Connection, payment_id: str) -> Optional[Pagamento]:
    row = conn.execute(
        "SELECT * FROM pagamentos WHERE payment_id = ?", (payment_id,)
    ).fetchone()
    return _row_to_pagamento(row) if row else None


def upsert_pagamento(conn: sqlite3.Connection, pagamento: Pagamento) -> None:
    conn.execute(
        """
        INSERT INTO pagamentos (payment_id, discord_id, valor, status, data_pagamento, processado)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(payment_id) DO UPDATE SET
            discord_id = excluded.discord_id,
            valor = excluded.valor,
            status = excluded.status,
            data_pagamento = excluded.data_pagamento,
            processado = excluded.processado
        """,
        (
            pagamento.payment_id,
            pagamento.discord_id,
            pagamento.valor,
            pagamento.status,
            _fmt_dt(pagamento.data_pagamento) or _fmt_dt(datetime.utcnow()),
            int(pagamento.processado),
        ),
    )
    conn.commit()


def listar_usuarios_expirados(conn: sqlite3.Connection, agora: datetime) -> list[Usuario]:
    rows = conn.execute(
        "SELECT * FROM usuarios WHERE status = 'ativo' AND data_expiracao <= ?",
        (_fmt_dt(agora),),
    ).fetchall()
    return [_row_to_usuario(r) for r in rows]


def listar_usuarios_a_vencer(
    conn: sqlite3.Connection, janela_inicio: datetime, janela_fim: datetime
) -> list[Usuario]:
    rows = conn.execute(
        "SELECT * FROM usuarios WHERE status = 'ativo' AND data_expiracao >= ? AND data_expiracao < ?",
        (_fmt_dt(janela_inicio), _fmt_dt(janela_fim)),
    ).fetchall()
    return [_row_to_usuario(r) for r in rows]
