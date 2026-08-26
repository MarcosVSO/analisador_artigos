"""Etapa 0 - validacao de viabilidade do projeto.

Responde as duas perguntas que decidem a arquitetura do resto do sistema:

  1. A minha chave da Scopus me da metadados uteis (com abstract)?
  2. Que fracao dos artigos da minha busca eu consigo baixar em PDF
     automaticamente, sem intervencao manual?

Nao grava nada no banco e nao faz parte do sistema final - e um diagnostico.
O resultado bruto vai para etapa0/resultado.json.

Uso:
    python etapa0/validar.py
    python etapa0/validar.py --amostra 25
    python etapa0/validar.py --query 'TITLE-ABS-KEY("foo") AND PUBYEAR > 2020'
    python etapa0/validar.py --sem-download    # nao baixa PDF de verdade
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

# Console do Windows costuma abrir em cp1252 e explodir nos acentos e nas
# molduras de caixa deste relatorio.
for fluxo in (sys.stdout, sys.stderr):
    try:
        fluxo.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

sys.path.insert(0, str(Path(__file__).resolve().parent))

from dotenv import load_dotenv  # noqa: E402

from resolvedor_pdf import baixar_e_validar, resolver  # noqa: E402
from scopus import (  # noqa: E402
    ClienteScopus,
    ScopusAuthError,
    ScopusEntitlementError,
    ScopusError,
    ScopusQuotaError,
    extrair_campos,
)

RAIZ = Path(__file__).resolve().parent.parent
SAIDA_JSON = RAIZ / "etapa0" / "resultado.json"

OK = "[ OK  ]"
AVISO = "[AVISO]"
FALHA = "[FALHA]"


# --------------------------------------------------------------------------
# Apresentacao
# --------------------------------------------------------------------------

def titulo(texto: str) -> None:
    print()
    print("=" * 74)
    print(f"  {texto}")
    print("=" * 74)


def linha(rotulo: str, valor: Any, marca: str = "") -> None:
    prefixo = f"{marca} " if marca else " " * 8
    print(f"{prefixo}{rotulo:<34} {valor}")


def barra(fracao: float, largura: int = 28) -> str:
    cheio = round(fracao * largura)
    return "#" * cheio + "." * (largura - cheio)


# --------------------------------------------------------------------------
# Testes
# --------------------------------------------------------------------------

def teste_a_autenticacao(cliente: ClienteScopus) -> dict[str, Any]:
    """Uma busca trivial so para saber se a chave responde e quanta quota resta."""
    titulo("TESTE A - autenticacao e quota")
    try:
        resp = cliente.buscar("TITLE-ABS-KEY(video)", count=1, view="STANDARD")
    except ScopusAuthError as exc:
        linha("Chave da Scopus", "rejeitada", FALHA)
        print(f"\n       {exc}")
        return {"ok": False, "motivo": "auth", "erro": str(exc)}
    except ScopusQuotaError as exc:
        linha("Chave da Scopus", "quota estourada", FALHA)
        print(f"\n       {exc}")
        return {"ok": False, "motivo": "quota", "erro": str(exc)}
    except ScopusError as exc:
        linha("Chave da Scopus", "erro", FALHA)
        print(f"\n       {exc}")
        return {"ok": False, "motivo": "erro", "erro": str(exc)}

    linha("Chave da Scopus", "aceita", OK)
    q = resp.quota
    linha("Quota semanal (limite)", q.limite if q.limite is not None else "nao informado")
    linha("Quota restante", q.restante if q.restante is not None else "nao informado")
    linha("Reseta em", q.reset_legivel)

    if q.restante is not None and q.restante < 100:
        linha("Atencao", "quota quase no fim - o teste C pode falhar", AVISO)

    return {
        "ok": True,
        "quota_limite": q.limite,
        "quota_restante": q.restante,
        "quota_reset": q.reset_legivel,
    }


def teste_b_view_completa(cliente: ClienteScopus) -> dict[str, Any]:
    """`view=COMPLETE` e o que traz abstract e keywords. Exige assinatura
    institucional; sem ela a API responde 403 e o projeto perde o abstract,
    que e justamente o insumo da triagem."""
    titulo("TESTE B - acesso a view=COMPLETE (abstract e keywords)")
    try:
        resp = cliente.buscar("TITLE-ABS-KEY(video)", count=1, view="COMPLETE")
    except ScopusEntitlementError as exc:
        linha("view=COMPLETE", "negada (403)", FALHA)
        print(f"\n       {exc}")
        print("       Provavel causa: fora da rede da universidade, ou a")
        print("       assinatura nao cobre a Search API. Ver SCOPUS_INSTTOKEN.")
        return {"ok": False, "view": "STANDARD", "erro": str(exc)}
    except ScopusError as exc:
        linha("view=COMPLETE", "erro", AVISO)
        print(f"\n       {exc}")
        return {"ok": False, "view": "STANDARD", "erro": str(exc)}

    tem_abstract = bool(resp.entradas and resp.entradas[0].get("dc:description"))
    linha("view=COMPLETE", "liberada", OK)
    linha(
        "Abstract no payload",
        "sim" if tem_abstract else "nao (campo vazio)",
        OK if tem_abstract else AVISO,
    )
    return {"ok": True, "view": "COMPLETE", "abstract_presente": tem_abstract}


def teste_c_busca_real(
    cliente: ClienteScopus, query: str, view: str, tamanho: int
) -> dict[str, Any]:
    """A busca de verdade: quantos artigos existem e quao completos vem."""
    titulo("TESTE C - string de busca real")
    print(f"       Query: {query[:200]}{'...' if len(query) > 200 else ''}")
    print()

    try:
        resp = cliente.buscar(query, count=min(tamanho, 25), view=view)
    except ScopusError as exc:
        linha("Busca", "falhou", FALHA)
        print(f"\n       {exc}")
        return {"ok": False, "erro": str(exc)}

    artigos = [extrair_campos(e) for e in resp.entradas]
    linha("Total de resultados", f"{resp.total:,}".replace(",", "."), OK)
    linha("Amostra recuperada", len(artigos))

    if resp.total == 0:
        linha("Diagnostico", "a query nao retornou nada - revise a sintaxe", FALHA)
        return {"ok": False, "total": 0, "artigos": []}
    if resp.total > 5000:
        linha("Nota", "acima de 5.000 -> paginacao por cursor obrigatoria", AVISO)

    if not artigos:
        return {"ok": True, "total": resp.total, "artigos": []}

    print()
    print("       Completude dos campos na amostra:")
    campos = ("doi", "titulo", "abstract", "keywords", "autores", "ano", "venue")
    completude: dict[str, float] = {}
    for campo in campos:
        preenchidos = sum(1 for a in artigos if a.get(campo))
        fracao = preenchidos / len(artigos)
        completude[campo] = round(fracao, 3)
        marca = OK if fracao >= 0.9 else (AVISO if fracao >= 0.5 else FALHA)
        print(
            f"  {marca} {campo:<12} {barra(fracao)} "
            f"{preenchidos:>3}/{len(artigos)}  ({fracao:.0%})"
        )

    anos = sorted(a["ano"] for a in artigos if a.get("ano"))
    if anos:
        print()
        linha("Faixa de anos na amostra", f"{anos[0]} - {anos[-1]}")

    venues = Counter(a["venue"] for a in artigos if a.get("venue"))
    if venues:
        print()
        print("       Veiculos mais frequentes na amostra:")
        for nome, n in venues.most_common(5):
            print(f"         {n:>2}x  {nome[:60]}")

    return {
        "ok": True,
        "total": resp.total,
        "view_usada": view,
        "completude": completude,
        "artigos": artigos,
    }


def teste_d_resolucao_pdf(
    artigos: list[dict[str, Any]],
    email: str,
    scopus_key: str,
    insttoken: str | None,
    baixar: bool,
) -> dict[str, Any]:
    """O numero que decide a Etapa 3: % de PDFs obtidos sem intervencao manual."""
    titulo("TESTE D - resolucao de PDF full-text")

    if not email:
        linha("CONTACT_EMAIL", "nao definido", FALHA)
        print("       O Unpaywall exige um e-mail de contato. Sem ele, so o")
        print("       OpenAlex e o arXiv respondem, e a taxa fica subestimada.")

    print(f"       Testando {len(artigos)} artigos (1-4 requisicoes cada)...")
    print()

    resultados = []
    por_fonte: Counter[str] = Counter()
    por_status: Counter[str] = Counter()

    for i, artigo in enumerate(artigos, 1):
        r = resolver(artigo, email, scopus_key, insttoken)
        por_status[r.status] += 1
        if r.fonte:
            por_fonte[r.fonte] += 1

        marca = OK if r.resolvido else AVISO
        rotulo = (artigo.get("titulo") or "(sem titulo)")[:48]
        origem = r.fonte or r.status
        print(f"  {marca} {i:>2}. {rotulo:<50} {origem}")

        resultados.append(
            {
                "titulo": artigo.get("titulo"),
                "doi": r.doi,
                "status": r.status,
                "fonte": r.fonte,
                "url": r.url,
                "detalhe": r.detalhe,
            }
        )

    resolvidos = por_status.get("aberto", 0)
    taxa = resolvidos / len(artigos) if artigos else 0.0

    print()
    linha("PDFs resolvidos", f"{resolvidos}/{len(artigos)}  ({taxa:.0%})")
    print(f"       {barra(taxa, 40)}")
    if por_fonte:
        print()
        print("       Por fonte:")
        for fonte, n in por_fonte.most_common():
            print(f"         {n:>2}  {fonte}")

    # Baixar de fato alguns confirma que a URL nao e uma pagina de login.
    downloads: list[dict[str, Any]] = []
    if baixar:
        candidatos = [r for r in resultados if r["status"] == "aberto" and r["url"]][:3]
        if candidatos:
            print()
            print("       Baixando 3 para confirmar que sao PDFs de verdade:")
            with tempfile.TemporaryDirectory() as tmp:
                for r in candidatos:
                    destino = str(Path(tmp) / "teste.pdf")
                    ok, tamanho, motivo = baixar_e_validar(r["url"], destino)
                    marca = OK if ok else FALHA
                    detalhe = f"{tamanho / 1024:.0f} KB" if ok else motivo
                    print(f"  {marca} {(r['titulo'] or '')[:48]:<50} {detalhe}")
                    downloads.append(
                        {"doi": r["doi"], "ok": ok, "bytes": tamanho, "motivo": motivo}
                    )

    return {
        "amostra": len(artigos),
        "resolvidos": resolvidos,
        "taxa": round(taxa, 3),
        "por_status": dict(por_status),
        "por_fonte": dict(por_fonte),
        "resultados": resultados,
        "downloads": downloads,
    }


# --------------------------------------------------------------------------
# Veredito
# --------------------------------------------------------------------------

def veredito(a: dict, b: dict, c: dict, d: dict | None) -> list[str]:
    titulo("VEREDITO")
    conclusoes: list[str] = []

    if not a.get("ok"):
        conclusoes.append(
            "BLOQUEADO: a chave da Scopus nao autenticou. Sem isso a Etapa 1 "
            "nao sai do lugar. Alternativa sem custo e sem chave: OpenAlex "
            "como fonte de descoberta."
        )
        for texto in conclusoes:
            print(f"  {FALHA} {texto}\n")
        return conclusoes

    if b.get("ok") and b.get("abstract_presente"):
        conclusoes.append(
            "Scopus OK com view=COMPLETE: metadados e abstract vem na propria "
            "busca. Segue o plano original da Etapa 1."
        )
    else:
        conclusoes.append(
            "Scopus autentica mas NAO entrega abstract na busca. Duas saidas: "
            "(a) buscar o abstract artigo a artigo na Abstract Retrieval API, "
            "1 requisicao extra por artigo; ou (b) usar o OpenAlex para "
            "enriquecer os metadados por DOI, de graca e sem quota. "
            "Recomendo (b) - e mais barato em quota e cobre mais editoras."
        )

    completude = c.get("completude") or {}
    cobertura_doi = completude.get("doi", 0)
    if cobertura_doi < 0.9 and c.get("ok"):
        conclusoes.append(
            f"So {cobertura_doi:.0%} da amostra tem DOI. Como o DOI e a chave "
            "de deduplicacao e de resolucao de PDF, os sem DOI vao precisar de "
            "casamento por titulo+ano na Etapa 1."
        )

    if d:
        taxa = d["taxa"]
        if taxa >= 0.6:
            conclusoes.append(
                f"Taxa de PDF automatico de {taxa:.0%}: boa. A Etapa 3 se paga "
                "e a fila manual fica administravel."
            )
        elif taxa >= 0.3:
            conclusoes.append(
                f"Taxa de PDF automatico de {taxa:.0%}: razoavel. Vale fazer a "
                "Etapa 3, mas ja planeje a tela de upload manual como parte "
                "central do fluxo, nao como excecao."
            )
        else:
            conclusoes.append(
                f"Taxa de PDF automatico de apenas {taxa:.0%}. Reduza a Etapa 3 "
                "a um resolvedor simples (so Unpaywall) e invista o tempo na "
                "tela de upload manual em lote - e por onde a maioria dos PDFs "
                "vai entrar de qualquer jeito."
            )
        if d["por_fonte"].get("sciencedirect"):
            conclusoes.append(
                "A ScienceDirect respondeu com PDF: voce TEM entitlement "
                "Elsevier. Vale manter esse resolvedor na cadeia."
            )

    for texto in conclusoes:
        print(f"  -> {texto}\n")
    return conclusoes


# --------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description="Etapa 0 - validacao de viabilidade")
    ap.add_argument("--query", help="sobrescreve SCOPUS_QUERY do .env")
    ap.add_argument("--amostra", type=int, help="sobrescreve AMOSTRA_PDF do .env")
    ap.add_argument(
        "--sem-download",
        action="store_true",
        help="nao baixa PDFs de verdade, so resolve as URLs",
    )
    args = ap.parse_args()

    load_dotenv(RAIZ / ".env")

    chave = os.getenv("SCOPUS_API_KEY", "").strip()
    insttoken = os.getenv("SCOPUS_INSTTOKEN", "").strip() or None
    email = os.getenv("CONTACT_EMAIL", "").strip()
    query = args.query or os.getenv("SCOPUS_QUERY", "").strip()
    amostra = args.amostra or int(os.getenv("AMOSTRA_PDF", "15"))

    print()
    print("  ETAPA 0 - VALIDACAO DE VIABILIDADE")
    print("  analisador_artigos")

    if not chave:
        print()
        print(f"  {FALHA} SCOPUS_API_KEY nao encontrada.")
        print("         Copie .env.example para .env e preencha a chave.")
        print("         Crie a chave em https://dev.elsevier.com/apikey/manage")
        return 1
    if not query:
        print()
        print(f"  {FALHA} SCOPUS_QUERY nao encontrada no .env.")
        return 1

    cliente = ClienteScopus(chave, insttoken)

    r_a = teste_a_autenticacao(cliente)
    if not r_a["ok"]:
        veredito(r_a, {}, {}, None)
        return 1

    r_b = teste_b_view_completa(cliente)
    r_c = teste_c_busca_real(cliente, query, r_b["view"], amostra)

    r_d = None
    artigos = (r_c.get("artigos") or [])[:amostra]
    if artigos:
        r_d = teste_d_resolucao_pdf(
            artigos, email, chave, insttoken, baixar=not args.sem_download
        )

    conclusoes = veredito(r_a, r_b, r_c, r_d)

    SAIDA_JSON.parent.mkdir(parents=True, exist_ok=True)
    SAIDA_JSON.write_text(
        json.dumps(
            {
                "query": query,
                "teste_a_autenticacao": r_a,
                "teste_b_view": r_b,
                "teste_c_busca": r_c,
                "teste_d_pdf": r_d,
                "conclusoes": conclusoes,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"  Resultado bruto salvo em {SAIDA_JSON.relative_to(RAIZ)}")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
