"""Contratos de entrada e saida da API (Pydantic)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PedidoBusca(BaseModel):
    """A busca traz todos os resultados da query e nao baixa nada.

    O download e sempre um passo separado, disparado pelo botao "Baixar
    pendentes" - assim voce ve o que veio antes de gastar tempo de rede.
    """

    query: str = Field(min_length=3, description="String de busca na sintaxe do Scopus")


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


class PaginaArtigos(BaseModel):
    """Uma pagina da listagem. `total` e a contagem APOS os filtros."""

    itens: list[ArtigoResposta]
    total: int
    pagina: int
    por_pagina: int
    paginas: int


class Progresso(BaseModel):
    busca_id: int
    total: int
    baixados: int
    pendentes: int
    paywall: int
    landing: int
    erro: int
    em_andamento: bool
    # Quantos o botao "Baixar pendentes" vai processar agora.
    a_baixar: int


class ConfiguracaoResposta(BaseModel):
    """O frontend usa isso para pre-preencher o campo e avisar se falta chave."""

    query_padrao: str
    credenciais_ok: bool
    aviso: str
    view_scopus: str
