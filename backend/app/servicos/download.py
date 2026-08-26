"""Download dos PDFs em background.

Roda num pool pequeno de threads. O progresso nao fica em memoria: e sempre
derivado da tabela `artigos`, entao sobrevive a um restart do servidor e nao
precisa de sincronizacao entre a thread do download e a do request.
"""

from __future__ import annotations

import logging
import threading
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import func, select

from .. import config
from ..banco import sessao_escopo
from ..modelos import Artigo, Busca, StatusBusca, StatusPDF
from .busca import nome_arquivo_pdf
from .resolvedor_pdf import baixar_e_validar, resolver

LOG = logging.getLogger(__name__)

# Evita que dois cliques no botao disparem dois downloads da mesma busca.
_buscas_ativas: set[int] = set()
_trava = threading.Lock()


def em_andamento(busca_id: int) -> bool:
    with _trava:
        return busca_id in _buscas_ativas


def _processar_artigo(artigo_id: int) -> None:
    """Resolve e baixa um artigo. Cada thread abre a propria sessao."""
    with sessao_escopo() as sessao:
        artigo = sessao.get(Artigo, artigo_id)
        if artigo is None or artigo.baixado:
            return
        dados = {"doi": artigo.doi, "titulo": artigo.titulo}
        destino = config.DIR_PDFS / nome_arquivo_pdf(artigo)

    resultado = resolver(
        dados,
        config.CONTACT_EMAIL,
        config.SCOPUS_API_KEY,
        config.SCOPUS_INSTTOKEN,
    )

    baixado = False
    tamanho = 0
    detalhe = resultado.detalhe

    if resultado.resolvido and resultado.url:
        baixado, tamanho, motivo = baixar_e_validar(resultado.url, destino)
        if not baixado:
            # A URL prometia PDF e nao entregou. Isso e o caso classico do
            # WAF da editora respondendo 403 - vale registrar o motivo exato
            # em vez de generalizar para "paywall".
            detalhe = f"resolvido em {resultado.fonte}, mas o download falhou: {motivo}"

    with sessao_escopo() as sessao:
        artigo = sessao.get(Artigo, artigo_id)
        if artigo is None:
            return
        artigo.pdf_fonte = resultado.fonte
        artigo.pdf_url = resultado.url
        artigo.pdf_detalhe = detalhe
        if baixado:
            artigo.baixado = True
            artigo.pdf_status = StatusPDF.BAIXADO.value
            artigo.pdf_caminho = str(destino.relative_to(config.RAIZ)).replace("\\", "/")
            artigo.pdf_bytes = tamanho
        else:
            artigo.baixado = False
            artigo.pdf_status = (
                StatusPDF.ERRO.value
                if resultado.resolvido
                else (resultado.status or StatusPDF.PAYWALL.value)
            )


def _processar_isolado(artigo_id: int) -> None:
    """Blindagem por artigo.

    `pool.map` propaga a primeira excecao e ABANDONA o resto da fila - foi
    assim que um TypeError num unico artigo deixou 4 outros presos em
    `pendente` para sempre. Um artigo problematico tem que virar uma linha
    com status `erro`, nunca derrubar o lote.
    """
    try:
        _processar_artigo(artigo_id)
    except Exception as exc:  # noqa: BLE001 - deliberadamente abrangente
        LOG.exception("Falha inesperada no artigo %s", artigo_id)
        try:
            with sessao_escopo() as sessao:
                artigo = sessao.get(Artigo, artigo_id)
                if artigo is not None and not artigo.baixado:
                    artigo.pdf_status = StatusPDF.ERRO.value
                    artigo.pdf_detalhe = f"erro interno: {type(exc).__name__}: {exc}"
        except Exception:  # noqa: BLE001
            LOG.exception("Nao consegui nem registrar o erro do artigo %s", artigo_id)


def _executar(busca_id: int) -> None:
    try:
        with sessao_escopo() as sessao:
            busca = sessao.get(Busca, busca_id)
            if busca is None:
                return
            busca.status = StatusBusca.BAIXANDO.value
            ids = list(
                sessao.scalars(
                    select(Artigo.id).where(
                        Artigo.busca_id == busca_id,
                        Artigo.baixado.is_(False),
                    )
                )
            )

        LOG.info("Iniciando download de %s artigos da busca %s", len(ids), busca_id)
        with ThreadPoolExecutor(max_workers=config.DOWNLOADS_SIMULTANEOS) as pool:
            list(pool.map(_processar_isolado, ids))

        with sessao_escopo() as sessao:
            busca = sessao.get(Busca, busca_id)
            if busca is not None:
                busca.status = StatusBusca.CONCLUIDA.value
    except Exception:  # noqa: BLE001 - a thread nao pode morrer em silencio
        LOG.exception("Download da busca %s falhou", busca_id)
        with sessao_escopo() as sessao:
            busca = sessao.get(Busca, busca_id)
            if busca is not None:
                busca.status = StatusBusca.ERRO.value
    finally:
        with _trava:
            _buscas_ativas.discard(busca_id)


def disparar(busca_id: int) -> bool:
    """Inicia o download em background. False se ja estava rodando."""
    with _trava:
        if busca_id in _buscas_ativas:
            return False
        _buscas_ativas.add(busca_id)

    thread = threading.Thread(
        target=_executar, args=(busca_id,), daemon=True, name=f"download-{busca_id}"
    )
    thread.start()
    return True


def progresso(sessao, busca_id: int) -> dict:
    """Contadores por status, lidos direto do banco."""
    linhas = sessao.execute(
        select(Artigo.pdf_status, func.count())
        .where(Artigo.busca_id == busca_id)
        .group_by(Artigo.pdf_status)
    ).all()
    por_status = {status: n for status, n in linhas}
    total = sum(por_status.values())
    return {
        "busca_id": busca_id,
        "total": total,
        "baixados": por_status.get(StatusPDF.BAIXADO.value, 0),
        "pendentes": por_status.get(StatusPDF.PENDENTE.value, 0),
        "paywall": por_status.get(StatusPDF.PAYWALL.value, 0),
        "landing": por_status.get(StatusPDF.LANDING.value, 0),
        "erro": por_status.get(StatusPDF.ERRO.value, 0),
        "em_andamento": em_andamento(busca_id),
    }
