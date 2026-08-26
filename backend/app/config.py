"""Configuracao central: caminhos do projeto e variaveis de ambiente.

Todos os diretorios de dados ficam sob `dados/`, na raiz do projeto, e sao
criados na importacao para que nenhum servico precise se preocupar com isso.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parents[2]

load_dotenv(RAIZ / ".env")

# --- Diretorios de dados -------------------------------------------------
DIR_DADOS = RAIZ / "dados"
DIR_PDFS = DIR_DADOS / "pdfs"
DIR_RESPOSTAS_SCOPUS = DIR_DADOS / "respostas_scopus"
CAMINHO_BANCO = DIR_DADOS / "analisador.db"

for _diretorio in (DIR_DADOS, DIR_PDFS, DIR_RESPOSTAS_SCOPUS):
    _diretorio.mkdir(parents=True, exist_ok=True)

URL_BANCO = f"sqlite:///{CAMINHO_BANCO}"

# --- Credenciais e parametros -------------------------------------------
SCOPUS_API_KEY = os.getenv("SCOPUS_API_KEY", "").strip()
SCOPUS_INSTTOKEN = os.getenv("SCOPUS_INSTTOKEN", "").strip() or None
CONTACT_EMAIL = os.getenv("CONTACT_EMAIL", "").strip()
SCOPUS_QUERY_PADRAO = os.getenv("SCOPUS_QUERY", "").strip()

# --- Analise por IA ------------------------------------------------------
# "claude_code" invoca a CLI do Claude Code em modo headless, usando o SEU
# login (assinatura Pro/Max). "api" usa a Anthropic API, que e cobrada por
# token e exige ANTHROPIC_API_KEY - util para processar em lote sem
# ninguem na frente.
MODO_ANALISE = os.getenv("MODO_ANALISE", "claude_code").strip()

# Caminho da CLI. Vazio = procurar no PATH.
CLAUDE_CLI = os.getenv("CLAUDE_CLI", "").strip()

# Modelo no modo claude_code. Vazio = respeita o padrao da sua CLI
# (o que voce escolheu em /model). Aceita alias: opus, sonnet, haiku.
MODELO_ANALISE_CLI = os.getenv("MODELO_ANALISE_CLI", "").strip()

# Um artigo longo obriga varias leituras de 20 paginas, entao a analise
# pode passar de dois minutos.
TIMEOUT_ANALISE_S = int(os.getenv("TIMEOUT_ANALISE_S", "600"))

# So usados no modo "api".
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()
MODELO_ANALISE = os.getenv("MODELO_ANALISE", "claude-opus-5").strip()

# A Etapa 0 mostrou que esta chave nao tem direito a view=COMPLETE (a Scopus
# responde 401 com "not authorized to access the requested view"). Entao a
# busca roda em STANDARD e o abstract vem do OpenAlex, que e gratuito e nao
# consome quota. Se um dia a assinatura liberar COMPLETE, basta trocar aqui.
SCOPUS_VIEW = os.getenv("SCOPUS_VIEW", "STANDARD").strip() or "STANDARD"

# A busca traz todos os resultados da query. Este teto nao e uma opcao de
# interface: e um freio para que uma query acidentalmente ampla ("streaming",
# sem mais nada) nao gaste a quota semanal inteira numa execucao.
LIMITE_SEGURANCA = int(os.getenv("LIMITE_SEGURANCA", "5000"))

# Quantos downloads simultaneos. Baixo de proposito: sao servidores de
# editora e repositorio, nao vale a pena ser agressivo.
DOWNLOADS_SIMULTANEOS = int(os.getenv("DOWNLOADS_SIMULTANEOS", "4"))


def credenciais_ok() -> tuple[bool, str]:
    """Checa o minimo para a busca funcionar, com mensagem acionavel."""
    if not SCOPUS_API_KEY:
        return False, (
            "SCOPUS_API_KEY nao configurada. Copie .env.example para .env e "
            "preencha a chave criada em https://dev.elsevier.com/apikey/manage"
        )
    return True, ""
