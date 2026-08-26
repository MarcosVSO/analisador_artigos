"""Rotas de busca: executar no Scopus, listar, trocar de linha e apagar."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from .. import config
from ..banco import obter_sessao
from ..esquemas import (
    BuscaResposta,
    ConfiguracaoResposta,
    PedidoBusca,
    Progresso,
    ResumoRemocao,
)
from ..modelos import Artigo, Busca, Resposta
from ..servicos import analise_claude_code, download
from ..servicos.busca import BuscaError, executar_busca

LOG = logging.getLogger(__name__)

roteador = APIRouter(prefix="/api", tags=["buscas"])


def _com_contadores(sessao: Session, buscas: list[Busca]) -> list[BuscaResposta]:
    """Anexa os contadores de cada linha de pesquisa.

    Tres consultas agregadas para a lista inteira, em vez de tres por linha -
    com dezenas de buscas a diferenca aparece.
    """
    if not buscas:
        return []
    ids = [b.id for b in buscas]

    totais = dict(
        sessao.execute(
            select(Artigo.busca_id, func.count())
            .where(Artigo.busca_id.in_(ids))
            .group_by(Artigo.busca_id)
        ).all()
    )
    baixados = dict(
        sessao.execute(
            select(Artigo.busca_id, func.count())
            .where(Artigo.busca_id.in_(ids), Artigo.baixado.is_(True))
            .group_by(Artigo.busca_id)
        ).all()
    )
    # So conta resposta com conteudo: uma linha vazia no banco nao e trabalho
    # feito, e e justamente o trabalho feito que a confirmacao precisa avisar.
    respondidas = dict(
        sessao.execute(
            select(Artigo.busca_id, func.count(Resposta.id))
            .join(Resposta, Resposta.artigo_id == Artigo.id)
            .where(Artigo.busca_id.in_(ids), func.trim(Resposta.texto) != "")
            .group_by(Artigo.busca_id)
        ).all()
    )

    saida = []
    for b in buscas:
        item = BuscaResposta.model_validate(b)
        item.artigos_total = totais.get(b.id, 0)
        item.artigos_baixados = baixados.get(b.id, 0)
        item.respostas_escritas = respondidas.get(b.id, 0)
        saida.append(item)
    return saida


@roteador.get("/configuracao", response_model=ConfiguracaoResposta)
def obter_configuracao() -> ConfiguracaoResposta:
    ok, aviso = config.credenciais_ok()
    pronta, analise_aviso = _analise_pronta()
    return ConfiguracaoResposta(
        query_padrao=config.SCOPUS_QUERY_PADRAO,
        credenciais_ok=ok,
        aviso=aviso,
        view_scopus=config.SCOPUS_VIEW,
        modo_analise=config.MODO_ANALISE,
        analise_pronta=pronta,
        analise_aviso=analise_aviso,
    )


def _analise_pronta() -> tuple[bool, str]:
    """Checa o pre-requisito do modo escolhido, para a tela avisar antes do
    clique em vez de so no erro."""
    if config.MODO_ANALISE == "claude_code":
        if analise_claude_code.localizar_cli(config.CLAUDE_CLI) is None:
            return False, analise_claude_code.INSTRUCAO_INSTALACAO
        return True, ""
    if not config.ANTHROPIC_API_KEY:
        return False, (
            "MODO_ANALISE=api exige ANTHROPIC_API_KEY no .env. Para usar sua "
            "assinatura em vez da API, deixe MODO_ANALISE=claude_code."
        )
    return True, ""


@roteador.post("/buscas", response_model=BuscaResposta, status_code=status.HTTP_201_CREATED)
def criar_busca(
    pedido: PedidoBusca, sessao: Session = Depends(obter_sessao)
) -> BuscaResposta:
    """Cria uma NOVA linha de pesquisa. As anteriores continuam intactas."""
    try:
        busca = executar_busca(sessao, pedido.query)
    except BuscaError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    return _com_contadores(sessao, [busca])[0]


@roteador.get("/buscas", response_model=list[BuscaResposta])
def listar_buscas(sessao: Session = Depends(obter_sessao)) -> list[BuscaResposta]:
    buscas = list(
        sessao.scalars(select(Busca).order_by(desc(Busca.criado_em)).limit(100))
    )
    return _com_contadores(sessao, buscas)


@roteador.get("/buscas/{busca_id}", response_model=BuscaResposta)
def obter_busca(
    busca_id: int, sessao: Session = Depends(obter_sessao)
) -> BuscaResposta:
    busca = sessao.get(Busca, busca_id)
    if busca is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Linha de pesquisa nao encontrada.")
    return _com_contadores(sessao, [busca])[0]


@roteador.delete("/buscas/{busca_id}", response_model=ResumoRemocao)
def remover_busca(
    busca_id: int, sessao: Session = Depends(obter_sessao)
) -> ResumoRemocao:
    """Apaga a linha de pesquisa, seus artigos, respostas e PDFs.

    Apaga SOMENTE os arquivos registrados em `pdf_caminho` dos artigos desta
    busca. Nunca varre `dados/pdfs/` - a pasta pode conter PDFs que voce pos
    ali a mao, e um `glob` levaria esses junto.
    """
    busca = sessao.get(Busca, busca_id)
    if busca is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Linha de pesquisa nao encontrada.")
    if download.em_andamento(busca_id):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Ha um download em andamento nesta linha de pesquisa. Espere terminar.",
        )

    artigos = list(sessao.scalars(select(Artigo).where(Artigo.busca_id == busca_id)))
    ids_artigos = [a.id for a in artigos]

    respostas_apagadas = 0
    if ids_artigos:
        respostas_apagadas = (
            sessao.scalar(
                select(func.count())
                .select_from(Resposta)
                .where(Resposta.artigo_id.in_(ids_artigos))
            )
            or 0
        )

    pdfs_apagados = 0
    for artigo in artigos:
        if not artigo.pdf_caminho:
            continue
        caminho = (config.RAIZ / artigo.pdf_caminho).resolve()
        # Mesma checagem de contencao do endpoint que serve o PDF: um campo
        # corrompido nao pode virar um delete em qualquer lugar do disco.
        if not caminho.is_relative_to(config.DIR_PDFS.resolve()):
            LOG.warning("Ignorando caminho fora de dados/pdfs: %s", artigo.pdf_caminho)
            continue
        try:
            if caminho.exists():
                caminho.unlink()
                pdfs_apagados += 1
        except OSError:
            LOG.exception("Nao consegui apagar %s", caminho)

    bruto_apagado = False
    if busca.arquivo_bruto:
        bruto = (config.RAIZ / busca.arquivo_bruto).resolve()
        if bruto.is_relative_to(config.DIR_RESPOSTAS_SCOPUS.resolve()):
            try:
                if bruto.exists():
                    bruto.unlink()
                    bruto_apagado = True
            except OSError:
                LOG.exception("Nao consegui apagar %s", bruto)

    # O cascade da relacao leva artigos e, por eles, as respostas.
    sessao.delete(busca)
    sessao.commit()

    return ResumoRemocao(
        busca_id=busca_id,
        artigos_removidos=len(artigos),
        pdfs_apagados=pdfs_apagados,
        respostas_apagadas=respostas_apagadas,
        arquivo_bruto_apagado=bruto_apagado,
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
