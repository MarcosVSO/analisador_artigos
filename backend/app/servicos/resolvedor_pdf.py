"""Cadeia de resolvedores de PDF full-text a partir de DOI/titulo.

Tres correcoes vieram do diagnostico da Etapa 0, que mediu 47% de resolucao
mas entregou 20% de PDF de verdade:

1. `best_oa_location.url` NAO e um PDF. Na maioria dos casos e um link
   `doi.org`, ou seja, a pagina do artigo. Aceitar isso como sucesso foi o
   que inflou a taxa. Agora so `url_for_pdf` conta como PDF; um link de
   pagina vira status `landing`, que e honesto sobre precisar de intervencao.
2. O Unpaywall devolve uma LISTA `oa_locations`, nao so a "melhor". A copia
   do repositorio (arXiv, institucional) costuma ter PDF direto quando a do
   editor nao tem, entao vale varrer todas.
3. Editora bloqueia cliente sem cara de navegador. Parte dos 403 era
   bot-blocking, nao paywall - dai os headers completos.

Nenhum resolvedor tenta contornar paywall. Sem versao aberta, o artigo fica
como `paywall` e espera upload manual.
"""

from __future__ import annotations

import re
import time
import unicodedata
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Any, Literal

import requests

Status = Literal["aberto", "landing", "paywall", "nao_encontrado", "erro"]

PREFIXOS_ELSEVIER = ("10.1016/", "10.1006/", "10.1053/", "10.1078/")

TIMEOUT = 20
INTERVALO = 0.15

# Sem isso, MDPI, IEEE e ACM respondem 403 a um cliente que se identifica
# como script. Nao e disfarce para burlar acesso - o conteudo ja e aberto;
# e so o minimo que os WAFs desses sites exigem para servir o arquivo.
CABECALHOS_NAVEGADOR = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "application/pdf,text/html;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,pt-BR;q=0.8",
}


@dataclass
class Candidato:
    fonte: str
    url: str
    direto: bool  # True = aponta para o arquivo; False = pagina do artigo


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


def _parece_pdf(url: str | None) -> bool:
    """Heuristica de forma da URL, usada como desempate.

    `doi.org` nunca serve arquivo - e um redirecionador para a pagina do
    editor, e foi a origem de todos os 403 do diagnostico.
    """
    if not url:
        return False
    baixa = url.lower()
    if "doi.org/" in baixa:
        return False
    return ".pdf" in baixa or "/pdf" in baixa


# --------------------------------------------------------------------------
# Resolvedores
# --------------------------------------------------------------------------

def via_unpaywall(doi: str, email: str) -> list[Candidato]:
    """Melhor cobertura de acesso aberto. Exige e-mail de contato.

    Varre todas as `oa_locations` porque a `best_oa_location` privilegia a
    versao publicada (frequentemente so pagina), enquanto o repositorio traz
    o arquivo.
    """
    if not email:
        return []
    resp = requests.get(
        f"https://api.unpaywall.org/v2/{doi}",
        params={"email": email},
        timeout=TIMEOUT,
    )
    if resp.status_code == 404:
        return []
    resp.raise_for_status()
    dados = resp.json()
    if not dados.get("is_oa"):
        return []

    locais = dados.get("oa_locations") or []
    melhor = dados.get("best_oa_location")
    if melhor and melhor not in locais:
        locais.insert(0, melhor)

    candidatos: list[Candidato] = []
    for local in locais:
        if not isinstance(local, dict):
            continue
        pdf = local.get("url_for_pdf")
        if pdf:
            candidatos.append(Candidato("unpaywall", pdf, direto=True))
        elif local.get("url"):
            candidatos.append(
                Candidato("unpaywall", local["url"], direto=_parece_pdf(local["url"]))
            )
    return candidatos


def via_openalex(doi: str, email: str) -> list[Candidato]:
    """No diagnostico nao acrescentou nenhum PDF alem dos do Unpaywall - o
    OpenAlex ingere os dados deles. Fica na cadeia porque as vezes indexa um
    `landing_page_url` de repositorio que o Unpaywall perdeu, e o custo e uma
    requisicao gratuita."""
    resp = requests.get(
        f"https://api.openalex.org/works/doi:{doi}",
        params={"mailto": email} if email else {},
        timeout=TIMEOUT,
    )
    if resp.status_code == 404:
        return []
    resp.raise_for_status()
    dados = resp.json()

    candidatos: list[Candidato] = []
    for local in dados.get("locations") or []:
        if not isinstance(local, dict) or not local.get("is_oa"):
            continue
        if local.get("pdf_url"):
            candidatos.append(Candidato("openalex", local["pdf_url"], direto=True))
        elif local.get("landing_page_url"):
            url = local["landing_page_url"]
            candidatos.append(Candidato("openalex", url, direto=_parece_pdf(url)))
    return candidatos


def via_arxiv(titulo: str) -> list[Candidato]:
    """Cobertura alta em redes e multimidia, onde o preprint sai antes.

    Casa por titulo normalizado exato. A API do arXiv nao indexa DOI de forma
    confiavel, e um match aproximado traria o artigo errado - o que e pior do
    que nao achar nada quando o PDF vai virar evidencia numa dissertacao.
    """
    if not titulo:
        return []
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
            href = link.get("href")
            # Element usa `[]` para indexar filhos, nao atributos - `link["href"]`
            # levanta TypeError em vez de ler o atributo.
            if link.get("title") == "pdf" and href:
                return [Candidato("arxiv", href, direto=True)]
    return []


def via_sciencedirect(
    doi: str, api_key: str, insttoken: str | None
) -> list[Candidato]:
    """Unica fonte para artigos Elsevier sob paywall, e so com entitlement.

    So dispara em DOI da Elsevier para nao gastar quota da Scopus a toa.
    """
    if not api_key or not doi.startswith(PREFIXOS_ELSEVIER):
        return []
    url = f"https://api.elsevier.com/content/article/doi/{doi}"
    cabecalhos = {"X-ELS-APIKey": api_key, "Accept": "application/pdf"}
    if insttoken:
        cabecalhos["X-ELS-Insttoken"] = insttoken
    resp = requests.get(url, headers=cabecalhos, timeout=TIMEOUT, stream=True)
    with resp:
        if resp.status_code != 200:
            return []
        inicio = next(resp.iter_content(8), b"")
    return [Candidato("sciencedirect", url, direto=True)] if inicio.startswith(b"%PDF") else []


# --------------------------------------------------------------------------
# Cadeia
# --------------------------------------------------------------------------

def resolver(
    artigo: dict[str, Any],
    email: str,
    scopus_api_key: str = "",
    insttoken: str | None = None,
) -> ResultadoPDF:
    """Junta os candidatos de todas as fontes e escolhe o melhor.

    Um PDF direto sempre ganha de uma pagina de artigo, venha de onde vier -
    por isso a coleta e completa antes da escolha, em vez de parar na
    primeira fonte que responder alguma coisa.
    """
    doi = (artigo.get("doi") or "").strip()
    titulo = artigo.get("titulo") or ""

    tentativas: list[tuple[str, Any]] = []
    if doi:
        tentativas.append(("unpaywall", lambda: via_unpaywall(doi, email)))
        tentativas.append(("openalex", lambda: via_openalex(doi, email)))
    tentativas.append(("arxiv", lambda: via_arxiv(titulo)))
    if doi:
        tentativas.append(
            ("sciencedirect", lambda: via_sciencedirect(doi, scopus_api_key, insttoken))
        )

    candidatos: list[Candidato] = []
    falhas: list[str] = []
    for nome, tentar in tentativas:
        time.sleep(INTERVALO)
        try:
            candidatos.extend(tentar())
        except (requests.RequestException, ET.ParseError, ValueError) as exc:
            falhas.append(f"{nome}: {type(exc).__name__}")

    diretos = [c for c in candidatos if c.direto]
    if diretos:
        melhor = diretos[0]
        return ResultadoPDF(doi or None, "aberto", melhor.fonte, melhor.url)

    if candidatos:
        melhor = candidatos[0]
        return ResultadoPDF(
            doi or None,
            "landing",
            melhor.fonte,
            melhor.url,
            detalhe="acesso aberto, mas so a pagina do artigo - sem link direto de PDF",
        )

    if falhas:
        return ResultadoPDF(doi or None, "paywall", detalhe="falhas -> " + "; ".join(falhas))
    if not doi:
        return ResultadoPDF(None, "nao_encontrado", detalhe="sem DOI e sem match no arXiv")
    return ResultadoPDF(doi, "paywall", detalhe="nenhuma versao aberta encontrada")


def baixar_e_validar(url: str, destino) -> tuple[bool, int, str]:
    """Baixa e confirma que e PDF pelos magic bytes.

    Servidor de editora devolve pagina de login com Content-Type
    application/pdf o tempo todo; so o cabecalho do arquivo nao mente. Grava
    em `.parcial` e so renomeia no fim, para que uma interrupcao no meio nao
    deixe um PDF truncado que o leitor de PDF vai aceitar em silencio.
    """
    from pathlib import Path

    destino = Path(destino)
    parcial = destino.with_suffix(destino.suffix + ".parcial")

    try:
        resp = requests.get(
            url,
            timeout=60,
            stream=True,
            allow_redirects=True,
            headers=CABECALHOS_NAVEGADOR,
        )
    except requests.RequestException as exc:
        return False, 0, f"falha de rede: {type(exc).__name__}"

    try:
        with resp:
            if resp.status_code != 200:
                return False, 0, f"HTTP {resp.status_code}"
            pedacos = resp.iter_content(64 * 1024)
            primeiro = next(pedacos, b"")
            if not primeiro.startswith(b"%PDF"):
                amostra = primeiro[:60].decode("utf-8", "replace").replace("\n", " ")
                return False, 0, f"nao e PDF (comeca com: {amostra!r})"
            tamanho = len(primeiro)
            destino.parent.mkdir(parents=True, exist_ok=True)
            with open(parcial, "wb") as saida:
                saida.write(primeiro)
                for pedaco in pedacos:
                    saida.write(pedaco)
                    tamanho += len(pedaco)
        parcial.replace(destino)
        return True, tamanho, "ok"
    except OSError as exc:
        return False, 0, f"falha ao gravar: {exc}"
    finally:
        parcial.unlink(missing_ok=True)
