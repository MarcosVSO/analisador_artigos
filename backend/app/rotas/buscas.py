"""Rotas de busca: executar no Scopus, listar e disparar downloads."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from .. import config
from ..banco import obter_sessao
from ..esquemas import BuscaResposta, ConfiguracaoResposta, PedidoBusca, Progresso
from ..modelos import Busca
from ..servicos import download
from ..servicos.busca import BuscaError, executar_busca

roteador = APIRouter(prefix="/api", tags=["buscas"])


@roteador.get("/configuracao", response_model=ConfiguracaoResposta)
def obter_configuracao() -> ConfiguracaoResposta:
    ok, aviso = config.credenciais_ok()
    return ConfiguracaoResposta(
        query_padrao=config.SCOPUS_QUERY_PADRAO,
        credenciais_ok=ok,
        aviso=aviso,
        view_scopus=config.SCOPUS_VIEW,
    )


@roteador.post("/buscas", response_model=BuscaResposta, status_code=status.HTTP_201_CREATED)
def criar_busca(
    pedido: PedidoBusca, sessao: Session = Depends(obter_sessao)
) -> Busca:
    """Busca no Scopus e persiste. Nao baixa nada - isso e o botao separado."""
    try:
        return executar_busca(sessao, pedido.query)
    except BuscaError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc


@roteador.get("/buscas", response_model=list[BuscaResposta])
def listar_buscas(sessao: Session = Depends(obter_sessao)) -> list[Busca]:
    return list(
        sessao.scalars(select(Busca).order_by(desc(Busca.criado_em)).limit(50))
    )


@roteador.post("/buscas/{busca_id}/baixar", response_model=Progresso)
def baixar_pdfs(
    busca_id: int,
    incluir_falhas: bool = False,
    limite: int | None = Query(default=None, ge=1, description="None = todos"),
    sessao: Session = Depends(obter_sessao),
) -> dict:
    """Baixa os pendentes.

    `limite` atende o "Baixar N pendentes"; `incluir_falhas` retenta tambem
    os que ficaram como paywall ou erro.
    """
    if sessao.get(Busca, busca_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Busca nao encontrada.")
    download.disparar(busca_id, incluir_falhas, limite)
    return download.progresso(sessao, busca_id)


@roteador.get("/buscas/{busca_id}/progresso", response_model=Progresso)
def obter_progresso(busca_id: int, sessao: Session = Depends(obter_sessao)) -> dict:
    if sessao.get(Busca, busca_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Busca nao encontrada.")
    return download.progresso(sessao, busca_id)
