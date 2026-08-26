"""Cliente minimo da Scopus Search API.

Escrito para a validacao da Etapa 0, mas ja no formato que a Etapa 1 vai
reaproveitar: erros tipados por causa (chave invalida x sem assinatura x
quota estourada) em vez de um `raise_for_status()` generico, porque cada um
desses casos leva a uma decisao de projeto diferente.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

import requests

BASE_URL = "https://api.elsevier.com/content/search/scopus"

# A Scopus permite ~9 req/s. Como aqui sao poucas requisicoes, um intervalo
# fixo generoso resolve sem precisar de um limitador de verdade.
INTERVALO_ENTRE_REQS = 0.3


class ScopusError(Exception):
    """Falha generica ao falar com a Scopus."""


class ScopusAuthError(ScopusError):
    """Chave ausente, invalida ou revogada (HTTP 401)."""


class ScopusEntitlementError(ScopusError):
    """A chave e valida mas nao tem direito de acesso a esse recurso (HTTP 403).

    E o caso classico de rodar de fora da rede da universidade sem insttoken,
    ou de pedir `view=COMPLETE` sem assinatura institucional.
    """


class ScopusQuotaError(ScopusError):
    """Quota semanal ou taxa por segundo estourada (HTTP 429)."""


@dataclass
class Quota:
    limite: int | None = None
    restante: int | None = None
    reset_epoch: int | None = None

    @property
    def reset_legivel(self) -> str:
        if self.reset_epoch is None:
            return "desconhecido"
        return time.strftime("%d/%m/%Y %H:%M", time.localtime(self.reset_epoch))


@dataclass
class RespostaBusca:
    total: int
    entradas: list[dict[str, Any]] = field(default_factory=list)
    quota: Quota = field(default_factory=Quota)
    view: str = "STANDARD"
    cursor_proximo: str | None = None


def _int_ou_none(valor: str | None) -> int | None:
    try:
        return int(valor)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


class ClienteScopus:
    def __init__(
        self,
        api_key: str,
        insttoken: str | None = None,
        timeout: int = 30,
    ) -> None:
        if not api_key:
            raise ScopusAuthError("SCOPUS_API_KEY nao definida.")
        self.timeout = timeout
        self.sessao = requests.Session()
        self.sessao.headers.update(
            {
                "X-ELS-APIKey": api_key,
                "Accept": "application/json",
                "User-Agent": "analisador-artigos/0.1 (revisao bibliografica)",
            }
        )
        if insttoken:
            self.sessao.headers["X-ELS-Insttoken"] = insttoken

    def buscar(
        self,
        query: str,
        count: int = 25,
        start: int = 0,
        view: str = "COMPLETE",
        cursor: str | None = None,
    ) -> RespostaBusca:
        """Executa uma busca. `view=COMPLETE` traz abstract e keywords, mas
        exige assinatura institucional e limita `count` a 25."""
        params: dict[str, Any] = {"query": query, "count": count, "view": view}
        # `cursor` e `start` sao mutuamente exclusivos na API.
        if cursor is not None:
            params["cursor"] = cursor
        else:
            params["start"] = start

        time.sleep(INTERVALO_ENTRE_REQS)
        try:
            resp = self.sessao.get(BASE_URL, params=params, timeout=self.timeout)
        except requests.RequestException as exc:
            raise ScopusError(f"Falha de rede ao chamar a Scopus: {exc}") from exc

        quota = Quota(
            limite=_int_ou_none(resp.headers.get("X-RateLimit-Limit")),
            restante=_int_ou_none(resp.headers.get("X-RateLimit-Remaining")),
            reset_epoch=_int_ou_none(resp.headers.get("X-RateLimit-Reset")),
        )

        if resp.status_code == 401:
            raise ScopusAuthError(f"401 - chave rejeitada. {_detalhe_erro(resp)}")
        if resp.status_code == 403:
            raise ScopusEntitlementError(
                f"403 - sem direito de acesso (view={view}). {_detalhe_erro(resp)}"
            )
        if resp.status_code == 429:
            raise ScopusQuotaError(
                f"429 - quota estourada. Reseta em {quota.reset_legivel}. "
                f"{_detalhe_erro(resp)}"
            )
        if resp.status_code >= 400:
            raise ScopusError(f"HTTP {resp.status_code}. {_detalhe_erro(resp)}")

        try:
            corpo = resp.json()["search-results"]
        except (ValueError, KeyError) as exc:
            raise ScopusError(f"Resposta em formato inesperado: {exc}") from exc

        entradas = corpo.get("entry") or []
        # Uma busca sem resultados vem como uma unica entrada com "error".
        if len(entradas) == 1 and "error" in entradas[0]:
            entradas = []

        return RespostaBusca(
            total=int(corpo.get("opensearch:totalResults", 0)),
            entradas=entradas,
            quota=quota,
            view=view,
            cursor_proximo=(corpo.get("cursor") or {}).get("@next"),
        )


def _detalhe_erro(resp: requests.Response) -> str:
    """Extrai a mensagem util do corpo de erro da Elsevier, que vem em pelo
    menos tres formatos diferentes dependendo da camada que falhou."""
    try:
        corpo = resp.json()
    except ValueError:
        return (resp.text or "")[:200]
    for caminho in (
        ("service-error", "status", "statusText"),
        ("error-response", "error-message"),
        ("message",),
    ):
        no: Any = corpo
        for chave in caminho:
            no = no.get(chave) if isinstance(no, dict) else None
            if no is None:
                break
        if isinstance(no, str):
            return no
    return str(corpo)[:200]


def extrair_campos(entrada: dict[str, Any]) -> dict[str, Any]:
    """Normaliza uma entrada crua da Scopus para o formato que o resto do
    projeto usa. Campos ausentes viram None em vez de sumirem, para que a
    contagem de completude seja honesta."""
    identificador = entrada.get("dc:identifier") or ""
    scopus_id = identificador.replace("SCOPUS_ID:", "") or None

    data_capa = entrada.get("prism:coverDate") or ""
    ano = _int_ou_none(data_capa[:4])

    autores = None
    if isinstance(entrada.get("author"), list):
        nomes = [a.get("authname") for a in entrada["author"] if a.get("authname")]
        autores = nomes or None
    elif entrada.get("dc:creator"):
        autores = [entrada["dc:creator"]]

    keywords = None
    if entrada.get("authkeywords"):
        keywords = [k.strip() for k in entrada["authkeywords"].split("|") if k.strip()]

    return {
        "scopus_id": scopus_id,
        "doi": entrada.get("prism:doi"),
        "titulo": entrada.get("dc:title"),
        "autores": autores,
        "ano": ano,
        "venue": entrada.get("prism:publicationName"),
        "abstract": entrada.get("dc:description"),
        "keywords": keywords,
        "citacoes": _int_ou_none(entrada.get("citedby-count")),
        "tipo": entrada.get("subtypeDescription"),
        "issn": entrada.get("prism:issn") or entrada.get("prism:eIssn"),
    }
