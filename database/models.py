"""
Modelos de dados: Usuario e Pagamento.

Implementados como dataclasses simples (sem ORM externo), já que o acesso ao
banco usa apenas `sqlite3` da biblioteca padrão. Isso reduz uma dependência
externa em um sistema que já depende de discord.py, fastapi e httpx.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Usuario:
    discord_id: str
    nome: Optional[str] = None
    data_inicio: Optional[datetime] = None
    data_expiracao: Optional[datetime] = None
    status: str = "inativo"  # "ativo" | "inativo"


@dataclass
class Pagamento:
    payment_id: str
    discord_id: str
    valor: float
    status: str = "pending"  # "pending" | "approved" | "valor_invalido" | "rejected"
    data_pagamento: Optional[datetime] = None
    processado: bool = False
