"""Rotas da sintese: matriz, exportacao e consultas sobre o conjunto."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from ..banco import obter_sessao
from ..esquemas import (
    ConsultaResposta,
    MatrizSintese,
    PedidoConsulta,
)
from ..modelos import Busca, Consulta
from ..servicos import sintese

roteador = APIRouter(prefix="/api/sintese", tags=["sintese"])


@roteador.get("", response_model=MatrizSintese)
def obter_matriz(
    busca_id: int | None = None,
    somente_analisados: bool = True,
    sessao: Session = Depends(obter_sessao),
) -> MatrizSintese:
    matriz = sintese.montar_matriz(sessao, busca_id, somente_analisados)
    return MatrizSintese.model_validate(matriz)


@roteador.get("/csv")
def exportar_csv(
    busca_id: int | None = None,
    somente_analisados: bool = True,
    sessao: Session = Depends(obter_sessao),
) -> Response:
    """Matriz em CSV, para levar direto para a planilha da dissertacao."""
    matriz = sintese.montar_matriz(sessao, busca_id, somente_analisados)
    if not matriz["artigos"]:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "Nao ha artigos para exportar."
        )
    carimbo = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")
    return Response(
        content=sintese.matriz_para_csv(matriz),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": (
                f'attachment; filename="matriz_sintese_{carimbo}.csv"'
            )
        },
    )


@roteador.get("/xlsx")
def exportar_xlsx(
    busca_id: int | None = None,
    somente_analisados: bool = True,
    sessao: Session = Depends(obter_sessao),
) -> Response:
    """Matriz em .xlsx, ja formatada para leitura."""
    matriz = sintese.montar_matriz(sessao, busca_id, somente_analisados)
    if not matriz["artigos"]:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "Nao ha artigos para exportar."
        )

    escopo = "Somente artigos analisados" if somente_analisados else "Todos os artigos"
    if busca_id is not None:
        busca = sessao.get(Busca, busca_id)
        if busca is not None:
            escopo += f" — linha de pesquisa: {busca.query}"
    else:
        escopo += " — todas as linhas de pesquisa"

    carimbo = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")
    return Response(
        content=sintese.matriz_para_xlsx(matriz, escopo),
        media_type=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
        headers={
            "Content-Disposition": (
                f'attachment; filename="matriz_sintese_{carimbo}.xlsx"'
            )
        },
    )


@roteador.get("/consultas", response_model=list[ConsultaResposta])
def listar_consultas(
    busca_id: int | None = None,
    limite: int = Query(default=50, ge=1, le=200),
    sessao: Session = Depends(obter_sessao),
) -> list[Consulta]:
    consulta = select(Consulta).order_by(desc(Consulta.criado_em)).limit(limite)
    if busca_id is not None:
        consulta = consulta.where(Consulta.busca_id == busca_id)
    return list(sessao.scalars(consulta))


@roteador.post(
    "/consultas", response_model=ConsultaResposta, status_code=status.HTTP_201_CREATED
)
def criar_consulta(
    pedido: PedidoConsulta, sessao: Session = Depends(obter_sessao)
) -> Consulta:
    """Pergunta sobre o conjunto das analises e guarda a resposta."""
    matriz = sintese.montar_matriz(
        sessao, pedido.busca_id, pedido.somente_analisados
    )
    try:
        texto, metadados = sintese.perguntar(matriz, pedido.pergunta)
    except sintese.SinteseError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc

    registro = Consulta(
        busca_id=pedido.busca_id,
        pergunta=pedido.pergunta.strip(),
        resposta=texto,
        artigos_considerados=len(matriz["artigos"]),
        modelo=metadados.get("modelo"),
        custo_usd=metadados.get("custo_usd"),
    )
    sessao.add(registro)
    sessao.commit()
    sessao.refresh(registro)
    return registro


@roteador.delete(
    "/consultas/{consulta_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
def remover_consulta(
    consulta_id: int, sessao: Session = Depends(obter_sessao)
) -> None:
    registro = sessao.get(Consulta, consulta_id)
    if registro is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Consulta nao encontrada.")
    sessao.delete(registro)
    sessao.commit()
