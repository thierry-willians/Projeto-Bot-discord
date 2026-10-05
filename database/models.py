from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Usuario:
    discord_id: str
    nome: Optional[str] = None
    data_inicio: Optional[datetime] = None
    data_expiracao: Optional[datetime] = None
    status: str = "inativo"


@dataclass
class Pagamento:
    payment_id: str
    discord_id: str
    valor: float
    status: str = "pending"
    data_pagamento: Optional[datetime] = None
    processado: bool = False


@dataclass
class RelatorioSemanal:
    id: Optional[int]
    semana_inicio: str
    semana_fim: str
    total_ids: int
    total_ofertas: int
    tempo_total_horas: float
    png_blob: bytes
    recebido_em: Optional[str] = None
    postado: bool = False
    postado_em: Optional[str] = None
    mensagem_id: Optional[str] = None
