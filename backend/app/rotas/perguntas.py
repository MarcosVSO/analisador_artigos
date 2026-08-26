"""CRUD das perguntas de pesquisa e das respostas por artigo."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..banco import obter_sessao
from ..esquemas import (
    ArtigoResposta,
    PainelRespostas,
    PatchPergunta,
    PedidoPergunta,
    PedidoResposta,
    PerguntaResposta,
    RespostaItem,
)
from ..modelos import Artigo, Pergunta, Resposta

roteador = APIRouter(prefix="/api", tags=["perguntas"])


@roteador.get("/perguntas", response_model=list[PerguntaResposta])
def listar_perguntas(
    incluir_inativas: bool = False, sessao: Session = Depends(obter_sessao)
) -> list[Pergunta]:
    consulta = select(Pergunta).order_by(Pergunta.ordem, Pergunta.id)
    if not incluir_inativas:
        consulta = consulta.where(Pergunta.ativa.is_(True))
    return list(sessao.scalars(consulta))


@roteador.post(
    "/perguntas", response_model=PerguntaResposta, status_code=status.HTTP_201_CREATED
)
def criar_pergunta(
    pedido: PedidoPergunta, sessao: Session = Depends(obter_sessao)
) -> Pergunta:
    # Nova pergunta entra no fim da lista.
    ultima = sessao.scalar(select(func.max(Pergunta.ordem))) or 0
    pergunta = Pergunta(texto=pedido.texto.strip(), ordem=ultima + 1)
    sessao.add(pergunta)
    sessao.commit()
    sessao.refresh(pergunta)
    return pergunta


@roteador.patch("/perguntas/{pergunta_id}", response_model=PerguntaResposta)
def atualizar_pergunta(
    pergunta_id: int,
    patch: PatchPergunta,
    sessao: Session = Depends(obter_sessao),
) -> Pergunta:
    pergunta = sessao.get(Pergunta, pergunta_id)
    if pergunta is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Pergunta nao encontrada.")
    if patch.texto is not None:
        pergunta.texto = patch.texto.strip()
    if patch.ordem is not None:
        pergunta.ordem = patch.ordem
    if patch.ativa is not None:
        pergunta.ativa = patch.ativa
    sessao.commit()
    sessao.refresh(pergunta)
    return pergunta


@roteador.delete(
    "/perguntas/{pergunta_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    # `response_model=None` explicito: o FastAPI infere o response model da
    # anotacao de retorno, e o `-> None` daqui vira `NoneType`, que e truthy.
    # Sem isso ele recusa a rota, porque um 204 nao pode ter corpo.
    response_model=None,
)
def remover_pergunta(
    pergunta_id: int, sessao: Session = Depends(obter_sessao)
) -> None:
    """Apaga de vez, junto com as respostas dela.

    Para tirar uma pergunta da tela sem perder o que ja foi respondido, use
    `PATCH {"ativa": false}` - e o que o botao "arquivar" faz.
    """
    pergunta = sessao.get(Pergunta, pergunta_id)
    if pergunta is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Pergunta nao encontrada.")
    sessao.delete(pergunta)
    sessao.commit()


@roteador.get("/artigos/{artigo_id}/respostas", response_model=PainelRespostas)
def obter_respostas(
    artigo_id: int, sessao: Session = Depends(obter_sessao)
) -> PainelRespostas:
    """Perguntas ativas + o que ja foi respondido para este artigo.

    Sempre devolve TODAS as perguntas ativas, com texto vazio nas ainda sem
    resposta - assim a tela e uma lista completa de campos, nao um retrato do
    que por acaso ja existe no banco.
    """
    artigo = sessao.get(Artigo, artigo_id)
    if artigo is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Artigo nao encontrado.")

    perguntas = list(
        sessao.scalars(
            select(Pergunta)
            .where(Pergunta.ativa.is_(True))
            .order_by(Pergunta.ordem, Pergunta.id)
        )
    )
    respostas = {
        r.pergunta_id: r.texto
        for r in sessao.scalars(
            select(Resposta).where(Resposta.artigo_id == artigo_id)
        )
    }

    itens = [
        RespostaItem(
            pergunta_id=p.id,
            pergunta_texto=p.texto,
            ordem=p.ordem,
            texto=respostas.get(p.id, ""),
        )
        for p in perguntas
    ]
    return PainelRespostas(
        artigo=ArtigoResposta.model_validate(artigo),
        itens=itens,
        respondidas=sum(1 for i in itens if i.texto.strip()),
    )


@roteador.put(
    "/artigos/{artigo_id}/respostas/{pergunta_id}", response_model=RespostaItem
)
def salvar_resposta(
    artigo_id: int,
    pergunta_id: int,
    pedido: PedidoResposta,
    sessao: Session = Depends(obter_sessao),
) -> RespostaItem:
    if sessao.get(Artigo, artigo_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Artigo nao encontrado.")
    pergunta = sessao.get(Pergunta, pergunta_id)
    if pergunta is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Pergunta nao encontrada.")

    resposta = sessao.scalar(
        select(Resposta).where(
            Resposta.artigo_id == artigo_id, Resposta.pergunta_id == pergunta_id
        )
    )
    if resposta is None:
        resposta = Resposta(artigo_id=artigo_id, pergunta_id=pergunta_id)
        sessao.add(resposta)
    resposta.texto = pedido.texto
    sessao.commit()

    return RespostaItem(
        pergunta_id=pergunta_id,
        pergunta_texto=pergunta.texto,
        ordem=pergunta.ordem,
        texto=resposta.texto,
    )
