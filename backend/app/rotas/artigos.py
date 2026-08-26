"""Rotas de artigos: listagem filtrada e abertura do PDF."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from .. import config
from ..banco import obter_sessao
from ..esquemas import ArtigoResposta
from ..modelos import Artigo

roteador = APIRouter(prefix="/api", tags=["artigos"])


@roteador.get("/artigos", response_model=list[ArtigoResposta])
def listar_artigos(
    busca_id: int | None = None,
    situacao: Literal["todos", "baixados", "sem_pdf"] = "todos",
    texto: str | None = Query(default=None, description="Filtra por titulo"),
    sessao: Session = Depends(obter_sessao),
) -> list[Artigo]:
    consulta = select(Artigo)
    if busca_id is not None:
        consulta = consulta.where(Artigo.busca_id == busca_id)
    if situacao == "baixados":
        consulta = consulta.where(Artigo.baixado.is_(True))
    elif situacao == "sem_pdf":
        consulta = consulta.where(Artigo.baixado.is_(False))
    if texto:
        consulta = consulta.where(Artigo.titulo.ilike(f"%{texto}%"))

    consulta = consulta.order_by(desc(Artigo.citacoes), desc(Artigo.ano))
    return list(sessao.scalars(consulta))


@roteador.get("/artigos/{artigo_id}/pdf")
def abrir_pdf(artigo_id: int, sessao: Session = Depends(obter_sessao)) -> FileResponse:
    """Serve o PDF para abrir em nova aba (inline, nao download)."""
    artigo = sessao.get(Artigo, artigo_id)
    if artigo is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Artigo nao encontrado.")
    if not artigo.baixado or not artigo.pdf_caminho:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "O PDF deste artigo ainda nao foi baixado."
        )

    caminho = (config.RAIZ / artigo.pdf_caminho).resolve()
    # Nunca servir nada fora de dados/pdfs, mesmo que o campo esteja corrompido.
    if not caminho.is_relative_to(config.DIR_PDFS.resolve()):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Caminho de arquivo invalido.")
    if not caminho.exists():
        raise HTTPException(
            status.HTTP_410_GONE,
            "O registro aponta para um PDF que nao esta mais no disco.",
        )

    return FileResponse(
        caminho,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{caminho.name}"'},
    )
