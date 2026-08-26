"""Contratos de entrada e saida da API (Pydantic)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PedidoBusca(BaseModel):
    query: str = Field(min_length=3, description="String de busca na sintaxe do Scopus")
    max_resultados: int = Field(default=200, ge=1, le=5000)
    baixar_automaticamente: bool = Field(
        default=True, description="Dispara o download dos PDFs assim que a busca terminar"
    )


class BuscaResposta(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    query: str
    total_scopus: int
    recuperados: int
    novos: int
    status: str
    arquivo_bruto: str | None
    criado_em: datetime


class ArtigoResposta(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    busca_id: int
    doi: str | None
    titulo: str
    autores: list[str] = []
    ano: int | None
    venue: str | None
    abstract: str | None
    keywords: list[str] = []
    citacoes: int | None
    tipo: str | None

    baixado: bool
    pdf_status: str
    pdf_fonte: str | None
    pdf_url: str | None
    pdf_bytes: int | None
    pdf_detalhe: str | None
    tem_paywall: bool


class Progresso(BaseModel):
    busca_id: int
    total: int
    baixados: int
    pendentes: int
    paywall: int
    landing: int
    erro: int
    em_andamento: bool


class ConfiguracaoResposta(BaseModel):
    """O frontend usa isso para pre-preencher o campo e avisar se falta chave."""

    query_padrao: str
    credenciais_ok: bool
    aviso: str
    view_scopus: str
