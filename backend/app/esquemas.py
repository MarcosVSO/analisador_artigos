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

    # Contadores calculados na hora - servem para a lista de linhas de
    # pesquisa mostrar o que cada uma tem antes de voce trocar ou apagar.
    artigos_total: int = 0
    artigos_baixados: int = 0
    respostas_escritas: int = 0


class ResumoRemocao(BaseModel):
    """O que uma exclusao de linha de pesquisa levou junto."""

    busca_id: int
    artigos_removidos: int
    pdfs_apagados: int
    respostas_apagadas: int
    arquivo_bruto_apagado: bool


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


class PedidoPergunta(BaseModel):
    texto: str = Field(min_length=3, max_length=2000)


class PatchPergunta(BaseModel):
    texto: str | None = Field(default=None, min_length=3, max_length=2000)
    ordem: int | None = None
    ativa: bool | None = None


class PerguntaResposta(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    texto: str
    ordem: int
    ativa: bool


class PedidoResposta(BaseModel):
    texto: str = Field(default="", max_length=20000)


class RespostaItem(BaseModel):
    """Uma pergunta ativa junto da resposta ja dada para este artigo."""

    pergunta_id: int
    pergunta_texto: str
    ordem: int
    texto: str


class PainelRespostas(BaseModel):
    artigo: ArtigoResposta
    itens: list[RespostaItem]
    respondidas: int


class ConfiguracaoResposta(BaseModel):
    """O frontend usa isso para pre-preencher o campo e avisar se falta chave."""

    query_padrao: str
    credenciais_ok: bool
    aviso: str
    view_scopus: str
