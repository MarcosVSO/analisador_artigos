"""Enriquecimento de metadados via OpenAlex.

Existe porque o diagnostico da Etapa 0 mostrou que esta chave da Scopus nao
tem direito a `view=COMPLETE`: a busca volta com 0% de abstract e 0% de
keywords. O OpenAlex preenche essa lacuna de graca, sem chave e sem quota,
e ainda casa por DOI - a mesma chave que a Scopus ja devolve.

Vantagem colateral sobre a `view=COMPLETE`: o OpenAlex tambem traz conceitos
e referencias, que vao ser uteis no dashboard da Etapa 7.
"""

from __future__ import annotations

import logging
from typing import Any

import requests

LOG = logging.getLogger(__name__)

URL_BASE = "https://api.openalex.org/works"
TIMEOUT = 30

# O filtro por DOI aceita varios valores separados por barra vertical. 50 e o
# teto pratico antes da URL ficar grande demais para o servidor deles.
LOTE = 50


def _reconstruir_abstract(indice: dict[str, list[int]] | None) -> str | None:
    """O OpenAlex nao guarda o abstract como texto.

    Por questao de licenciamento, eles armazenam um indice invertido
    (palavra -> posicoes onde ela aparece). Reconstruir e so espalhar cada
    palavra nas suas posicoes e ler na ordem.
    """
    if not indice:
        return None
    posicoes: list[tuple[int, str]] = []
    for palavra, ocorrencias in indice.items():
        for posicao in ocorrencias:
            posicoes.append((posicao, palavra))
    if not posicoes:
        return None
    posicoes.sort()
    return " ".join(palavra for _, palavra in posicoes)


def _extrair(trabalho: dict[str, Any]) -> dict[str, Any]:
    conceitos = [
        c.get("display_name")
        for c in (trabalho.get("concepts") or [])
        if c.get("display_name") and (c.get("score") or 0) >= 0.3
    ]
    return {
        "abstract": _reconstruir_abstract(trabalho.get("abstract_inverted_index")),
        "keywords": conceitos or None,
    }


def enriquecer(artigos: list[dict[str, Any]], email: str) -> int:
    """Preenche abstract e keywords, no lugar, para os artigos que tem DOI.

    Devolve quantos foram efetivamente enriquecidos. Falha de rede aqui nao
    e fatal: o artigo segue sem abstract e a busca continua valendo.
    """
    por_doi = {
        (a.get("doi") or "").lower(): a for a in artigos if a.get("doi")
    }
    if not por_doi:
        return 0

    dois = list(por_doi)
    enriquecidos = 0

    for inicio in range(0, len(dois), LOTE):
        fatia = dois[inicio : inicio + LOTE]
        params = {
            "filter": "doi:" + "|".join(fatia),
            "per-page": LOTE,
            "select": "doi,abstract_inverted_index,concepts",
        }
        if email:
            params["mailto"] = email

        try:
            resp = requests.get(URL_BASE, params=params, timeout=TIMEOUT)
            resp.raise_for_status()
            resultados = resp.json().get("results") or []
        except (requests.RequestException, ValueError) as exc:
            LOG.warning("OpenAlex falhou no lote %s: %s", inicio // LOTE, exc)
            continue

        for trabalho in resultados:
            # O OpenAlex devolve o DOI como URL completa.
            doi = (trabalho.get("doi") or "").lower().replace("https://doi.org/", "")
            artigo = por_doi.get(doi)
            if artigo is None:
                continue
            campos = _extrair(trabalho)
            for chave, valor in campos.items():
                if valor and not artigo.get(chave):
                    artigo[chave] = valor
                    if chave == "abstract":
                        enriquecidos += 1

    return enriquecidos
