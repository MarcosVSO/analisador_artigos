"""Cadeia de resolvedores de PDF full-text a partir de um DOI/titulo.

A ordem importa: tenta primeiro as fontes que dao o PDF direto e de graca,
e so entao a da Elsevier, que consome a mesma quota da busca no Scopus.

Nenhum resolvedor tenta contornar paywall. Quando o artigo nao tem versao
aberta, o resultado e `paywall` e ele vai para a fila de upload manual.
"""

from __future__ import annotations

import re
import time
import unicodedata
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Any, Literal

import requests

Status = Literal["aberto", "paywall", "nao_encontrado", "erro"]

# Prefixos DOI da Elsevier. So vale gastar quota na API da ScienceDirect
# quando o DOI e de fato deles.
PREFIXOS_ELSEVIER = ("10.1016/", "10.1006/", "10.1053/", "10.1078/")

TIMEOUT = 20
INTERVALO = 0.15

USER_AGENT = "analisador-artigos/0.1 (revisao bibliografica)"


@dataclass
class ResultadoPDF:
    doi: str | None
    status: Status
    fonte: str | None = None
    url: str | None = None
    detalhe: str | None = None

    @property
    def resolvido(self) -> bool:
        return self.status == "aberto"


def _normalizar_titulo(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto or "")
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", texto.lower()).strip()


# --------------------------------------------------------------------------
# Resolvedores individuais. Cada um devolve (fonte, url) ou None.
# --------------------------------------------------------------------------

def via_unpaywall(doi: str, email: str) -> tuple[str, str] | None:
    """Unpaywall: a melhor cobertura de acesso aberto. Exige um e-mail de
    contato como parametro - e a forma deles de rastrear abuso."""
    if not email:
        return None
    resp = requests.get(
        f"https://api.unpaywall.org/v2/{doi}",
        params={"email": email},
        timeout=TIMEOUT,
    )
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    dados = resp.json()
    if not dados.get("is_oa"):
        return None
    melhor = dados.get("best_oa_location") or {}
    pdf = melhor.get("url_for_pdf") or melhor.get("url")
    return ("unpaywall", pdf) if pdf else None


def via_openalex(doi: str, email: str) -> tuple[str, str] | None:
    """OpenAlex: cobertura parecida com a do Unpaywall, mas as vezes acha
    um repositorio que o outro nao indexou. O `mailto` poe a requisicao no
    polite pool, com rate limit melhor."""
    resp = requests.get(
        f"https://api.openalex.org/works/doi:{doi}",
        params={"mailto": email} if email else {},
        timeout=TIMEOUT,
    )
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    dados = resp.json()
    melhor = dados.get("best_oa_location") or {}
    pdf = melhor.get("pdf_url") or (dados.get("open_access") or {}).get("oa_url")
    return ("openalex", pdf) if pdf else None


def via_arxiv(titulo: str) -> tuple[str, str] | None:
    """arXiv: cobertura alta em redes e multimidia, justamente onde o
    preprint costuma sair antes da versao da conferencia.

    Casa por titulo normalizado - a API nao indexa DOI de forma confiavel.
    Exige correspondencia exata do titulo normalizado para evitar trazer um
    artigo parecido, que seria pior que nao achar nada.
    """
    if not titulo:
        return None
    resp = requests.get(
        "http://export.arxiv.org/api/query",
        params={"search_query": 'ti:"' + titulo + '"', "max_results": 3},
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    ns = {"a": "http://www.w3.org/2005/Atom"}
    raiz = ET.fromstring(resp.text)
    alvo = _normalizar_titulo(titulo)
    for entrada in raiz.findall("a:entry", ns):
        achado = (entrada.findtext("a:title", default="", namespaces=ns) or "").strip()
        if _normalizar_titulo(achado) != alvo:
            continue
        for link in entrada.findall("a:link", ns):
            if link.get("title") == "pdf":
                return ("arxiv", link.get("href"))
    return None


def via_sciencedirect(
    doi: str, api_key: str, insttoken: str | None
) -> tuple[str, str] | None:
    """ScienceDirect Article Retrieval API: unica fonte para artigos Elsevier
    sob paywall, e so funciona com entitlement institucional.

    Faz um GET com Accept: application/pdf e checa os primeiros bytes. Um 200
    com corpo HTML e a assinatura classica de "sem direito de acesso".
    """
    if not api_key or not doi.startswith(PREFIXOS_ELSEVIER):
        return None
    url = f"https://api.elsevier.com/content/article/doi/{doi}"
    cabecalhos = {"X-ELS-APIKey": api_key, "Accept": "application/pdf"}
    if insttoken:
        cabecalhos["X-ELS-Insttoken"] = insttoken
    resp = requests.get(url, headers=cabecalhos, timeout=TIMEOUT, stream=True)
    with resp:
        if resp.status_code != 200:
            return None
        inicio = next(resp.iter_content(8), b"")
    return ("sciencedirect", url) if inicio.startswith(b"%PDF") else None


# --------------------------------------------------------------------------
# Cadeia
# --------------------------------------------------------------------------

def resolver(
    artigo: dict[str, Any],
    email: str,
    scopus_api_key: str = "",
    insttoken: str | None = None,
) -> ResultadoPDF:
    doi = (artigo.get("doi") or "").strip()
    titulo = artigo.get("titulo") or ""

    if not doi:
        # Sem DOI ainda da para tentar o arXiv pelo titulo.
        try:
            achado = via_arxiv(titulo)
        except (requests.RequestException, ET.ParseError) as exc:
            return ResultadoPDF(None, "erro", detalhe=f"arxiv: {exc}")
        if achado:
            return ResultadoPDF(None, "aberto", fonte=achado[0], url=achado[1])
        return ResultadoPDF(
            None, "nao_encontrado", detalhe="sem DOI e sem match no arXiv"
        )

    tentativas = (
        ("unpaywall", lambda: via_unpaywall(doi, email)),
        ("openalex", lambda: via_openalex(doi, email)),
        ("arxiv", lambda: via_arxiv(titulo)),
        ("sciencedirect", lambda: via_sciencedirect(doi, scopus_api_key, insttoken)),
    )

    falhas: list[str] = []
    for nome, tentar in tentativas:
        time.sleep(INTERVALO)
        try:
            achado = tentar()
        except (requests.RequestException, ET.ParseError) as exc:
            falhas.append(f"{nome}: {type(exc).__name__}")
            continue
        if achado:
            return ResultadoPDF(doi, "aberto", fonte=achado[0], url=achado[1])

    detalhe = (
        "falhas -> " + "; ".join(falhas)
        if falhas
        else "nenhuma fonte aberta encontrada"
    )
    return ResultadoPDF(doi, "paywall", detalhe=detalhe)


def baixar_e_validar(url: str, destino: str) -> tuple[bool, int, str]:
    """Baixa e confirma que e PDF de verdade pelos magic bytes.

    Servidor de editora devolve pagina de login com Content-Type
    application/pdf o tempo todo; so o cabecalho do arquivo nao mente.
    """
    try:
        resp = requests.get(
            url,
            timeout=60,
            stream=True,
            allow_redirects=True,
            headers={"User-Agent": USER_AGENT},
        )
    except requests.RequestException as exc:
        return False, 0, f"falha de rede: {exc}"

    with resp:
        if resp.status_code != 200:
            return False, 0, f"HTTP {resp.status_code}"
        pedacos = resp.iter_content(64 * 1024)
        primeiro = next(pedacos, b"")
        if not primeiro.startswith(b"%PDF"):
            amostra = primeiro[:60].decode("utf-8", "replace").replace("\n", " ")
            return False, 0, f"nao e PDF (comeca com: {amostra!r})"
        tamanho = len(primeiro)
        with open(destino, "wb") as saida:
            saida.write(primeiro)
            for pedaco in pedacos:
                saida.write(pedaco)
                tamanho += len(pedaco)
    return True, tamanho, "ok"
