"""Execucao de uma busca: Scopus -> arquivo bruto -> OpenAlex -> SQLite."""

from __future__ import annotations

import json
import logging
import re
import unicodedata
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from .. import config
from ..modelos import Artigo, Busca, StatusBusca, StatusPDF
from . import openalex
from .scopus import ClienteScopus, ScopusError, extrair_campos

LOG = logging.getLogger(__name__)

# A view STANDARD aceita ate 200 por requisicao; 25 e o teto da COMPLETE.
# Como a Etapa 0 mostrou que so temos STANDARD, da para pedir paginas grandes.
POR_PAGINA = 100


class BuscaError(Exception):
    """Falha que o usuario precisa ver no frontend."""


def _slug(texto: str, limite: int = 60) -> str:
    texto = unicodedata.normalize("NFKD", texto or "")
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = re.sub(r"[^A-Za-z0-9]+", "-", texto).strip("-").lower()
    return texto[:limite] or "sem-titulo"


def _normalizar_doi(doi: str | None) -> str | None:
    if not doi:
        return None
    doi = doi.strip().lower()
    for prefixo in ("https://doi.org/", "http://doi.org/", "doi:"):
        if doi.startswith(prefixo):
            doi = doi[len(prefixo) :]
    return doi or None


def _salvar_resposta_bruta(query: str, paginas: list[dict[str, Any]]) -> str:
    """Grava a resposta crua da Scopus antes de qualquer transformacao.

    Serve de auditoria (dá para reprocessar sem gastar quota) e de prova de
    procedencia dos dados na dissertacao.
    """
    carimbo = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    caminho = config.DIR_RESPOSTAS_SCOPUS / f"busca_{carimbo}.json"
    caminho.write_text(
        json.dumps(
            {
                "query": query,
                "executada_em": datetime.now(timezone.utc).isoformat(),
                "view": config.SCOPUS_VIEW,
                "paginas": paginas,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return str(caminho.relative_to(config.RAIZ)).replace("\\", "/")


def executar_busca(sessao: Session, query: str, max_resultados: int) -> Busca:
    ok, motivo = config.credenciais_ok()
    if not ok:
        raise BuscaError(motivo)
    if not query.strip():
        raise BuscaError("A string de busca esta vazia.")

    cliente = ClienteScopus(config.SCOPUS_API_KEY, config.SCOPUS_INSTTOKEN)

    paginas_brutas: list[dict[str, Any]] = []
    entradas: list[dict[str, Any]] = []
    total = 0
    inicio = 0

    try:
        while inicio < max_resultados:
            quantidade = min(POR_PAGINA, max_resultados - inicio)
            resposta = cliente.buscar(
                query, count=quantidade, start=inicio, view=config.SCOPUS_VIEW
            )
            total = resposta.total
            paginas_brutas.append({"start": inicio, "entradas": resposta.entradas})
            entradas.extend(resposta.entradas)

            inicio += len(resposta.entradas)
            if not resposta.entradas or inicio >= total:
                break
            # A Scopus limita paginacao por `start` a 5.000 resultados.
            if inicio >= 5000:
                LOG.warning("Limite de 5.000 da paginacao por start atingido.")
                break
    except ScopusError as exc:
        raise BuscaError(str(exc)) from exc

    artigos = [extrair_campos(e) for e in entradas]
    for artigo in artigos:
        artigo["doi"] = _normalizar_doi(artigo.get("doi"))

    arquivo_bruto = _salvar_resposta_bruta(query, paginas_brutas)

    # Sem view=COMPLETE, o abstract so existe se o OpenAlex trouxer.
    try:
        enriquecidos = openalex.enriquecer(artigos, config.CONTACT_EMAIL)
        LOG.info("OpenAlex preencheu abstract de %s artigos", enriquecidos)
    except Exception:  # noqa: BLE001 - enriquecimento nunca derruba a busca
        LOG.exception("Falha ao enriquecer via OpenAlex; seguindo sem abstract")

    busca = Busca(
        query=query,
        total_scopus=total,
        recuperados=len(artigos),
        status=StatusBusca.CONCLUIDA.value,
        arquivo_bruto=arquivo_bruto,
    )
    sessao.add(busca)
    sessao.flush()  # precisa do id para as FKs

    vistos: set[str] = set()
    novos = 0
    for dados in artigos:
        doi = dados.get("doi")
        # Dedup dentro da busca. Sem DOI, cai para titulo+ano normalizados.
        chave = doi or f"{_slug(dados.get('titulo') or '')}|{dados.get('ano')}"
        if chave in vistos:
            continue
        vistos.add(chave)

        sessao.add(
            Artigo(
                busca_id=busca.id,
                scopus_id=dados.get("scopus_id"),
                doi=doi,
                titulo=dados.get("titulo") or "(sem titulo)",
                autores=dados.get("autores") or [],
                ano=dados.get("ano"),
                venue=dados.get("venue"),
                abstract=dados.get("abstract"),
                keywords=dados.get("keywords") or [],
                citacoes=dados.get("citacoes"),
                tipo=dados.get("tipo"),
                pdf_status=StatusPDF.PENDENTE.value,
            )
        )
        novos += 1

    busca.novos = novos
    sessao.commit()
    sessao.refresh(busca)
    return busca


def nome_arquivo_pdf(artigo: Artigo) -> str:
    """Nome legivel ao navegar a pasta, e unico pelo id."""
    ano = artigo.ano or "sd"
    return f"{ano}_{_slug(artigo.titulo, 60)}_{artigo.id}.pdf"
