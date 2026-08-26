"""Rotas de artigos: listagem paginada com filtros e abertura do PDF."""

from __future__ import annotations

import math
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy import asc, desc, func, select
from sqlalchemy.orm import Session

from .. import config
from ..banco import obter_sessao
from ..esquemas import ArtigoResposta, PaginaArtigos
from ..modelos import Artigo, StatusPDF
from ..servicos import download

roteador = APIRouter(prefix="/api", tags=["artigos"])

# Do ponto de vista de quem vai ler, "tem paywall" e todo artigo cujo PDF nao
# veio sozinho - inclusive o `landing`, onde existe versao aberta mas so a
# pagina do artigo.
STATUS_PAYWALL = (StatusPDF.PAYWALL.value, StatusPDF.LANDING.value)

Ordenacao = Literal["citacoes", "ano_desc", "ano_asc", "titulo"]

# `Artigo.id` no fim de toda ordenacao: sem um criterio de desempate estavel,
# duas paginas consecutivas podem repetir ou pular um artigo quando varios
# empatam no mesmo ano.
ORDENS = {
    "citacoes": (desc(Artigo.citacoes), desc(Artigo.ano), Artigo.id),
    "ano_desc": (desc(Artigo.ano), desc(Artigo.citacoes), Artigo.id),
    "ano_asc": (asc(Artigo.ano), desc(Artigo.citacoes), Artigo.id),
    "titulo": (asc(Artigo.titulo), Artigo.id),
}


@roteador.get("/artigos", response_model=PaginaArtigos)
def listar_artigos(
    busca_id: int | None = None,
    baixado: bool | None = Query(default=None, description="None = ambos"),
    paywall: bool | None = Query(default=None, description="None = ambos"),
    texto: str | None = Query(default=None, description="Filtra por titulo"),
    ordenar_por: Ordenacao = "citacoes",
    pagina: int = Query(default=1, ge=1),
    por_pagina: int = Query(default=15, ge=1, le=100),
    sessao: Session = Depends(obter_sessao),
) -> PaginaArtigos:
    filtros = []
    if busca_id is not None:
        filtros.append(Artigo.busca_id == busca_id)
    if baixado is not None:
        filtros.append(Artigo.baixado.is_(baixado))
    if paywall is not None:
        condicao = Artigo.pdf_status.in_(STATUS_PAYWALL)
        filtros.append(condicao if paywall else ~condicao)
    if texto:
        filtros.append(Artigo.titulo.ilike(f"%{texto}%"))

    # A contagem precisa dos mesmos filtros da pagina, senao a paginacao
    # mente sobre quantas paginas existem.
    total = sessao.scalar(select(func.count()).select_from(Artigo).where(*filtros)) or 0

    itens = list(
        sessao.scalars(
            select(Artigo)
            .where(*filtros)
            .order_by(*ORDENS[ordenar_por])
            .offset((pagina - 1) * por_pagina)
            .limit(por_pagina)
        )
    )

    return PaginaArtigos(
        itens=[ArtigoResposta.model_validate(a) for a in itens],
        total=total,
        pagina=pagina,
        por_pagina=por_pagina,
        paginas=max(1, math.ceil(total / por_pagina)),
    )


@roteador.get("/artigos/{artigo_id}", response_model=ArtigoResposta)
def detalhar_artigo(
    artigo_id: int, sessao: Session = Depends(obter_sessao)
) -> Artigo:
    """Detalhe completo, usado pelo modal da lupa."""
    artigo = sessao.get(Artigo, artigo_id)
    if artigo is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Artigo nao encontrado.")
    return artigo


@roteador.post("/artigos/{artigo_id}/baixar", response_model=ArtigoResposta)
def baixar_artigo(
    artigo_id: int, sessao: Session = Depends(obter_sessao)
) -> Artigo:
    """Dispara a aquisicao do PDF de um artigo so (o botao da linha)."""
    artigo = sessao.get(Artigo, artigo_id)
    if artigo is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Artigo nao encontrado.")
    if artigo.baixado:
        raise HTTPException(status.HTTP_409_CONFLICT, "Este PDF ja foi baixado.")
    download.disparar_artigo(artigo_id)
    return artigo


@roteador.get("/artigos/{artigo_id}/pdf")
def abrir_pdf(
    artigo_id: int,
    anexo: bool = Query(default=False, description="true = salvar em vez de abrir"),
    sessao: Session = Depends(obter_sessao),
) -> FileResponse:
    """Serve o PDF. Inline por padrao; com `anexo=true`, forca o salvamento."""
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

    disposicao = "attachment" if anexo else "inline"
    return FileResponse(
        caminho,
        media_type="application/pdf",
        headers={"Content-Disposition": f'{disposicao}; filename="{caminho.name}"'},
    )
