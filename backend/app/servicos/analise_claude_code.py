"""Analise do artigo invocando a CLI do Claude Code em modo headless.

Usa o login da sua assinatura, nao a API cobrada por token. Dois detalhes da
documentacao mandam no desenho aqui:

- **Sem `--bare`.** O modo bare acelera a partida, mas nao le as credenciais
  OAuth: exigiria ANTHROPIC_API_KEY e derrubaria justamente o motivo de usar
  esta rota. O custo e uma partida mais lenta, porque a sessao carrega hooks,
  CLAUDE.md e servidores MCP do ambiente.
- **Permissao explicita.** Em `-p` a sessao comeca no modo Manual em todos os
  planos. Sem `--allowedTools "Read"` a leitura do PDF pararia num pedido de
  permissao que ninguem vai responder, e o processo ficaria pendurado ate o
  timeout.
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from .. import config

LOG = logging.getLogger(__name__)

RAIZ = config.RAIZ

# Diretorio de trabalho das sessoes headless, FORA do projeto.
#
# Rodando na raiz do projeto, a sessao carrega a auto-memoria daquele caminho.
# Medido aqui: as notas de roadmap do assistente entravam no contexto e
# apareciam na resposta da sintese ("as proximas etapas do roadmap 4-9"),
# misturando anotacoes de desenvolvimento com a revisao bibliografica do
# usuario. De um diretorio neutro nada disso e carregado.
PASTA_SESSAO = Path(tempfile.gettempdir()) / "analisador_artigos_sessao"

# Tudo o que uma leitura de PDF nao precisa. Cada definicao de ferramenta
# entra no contexto de toda invocacao, entao podar aqui e economia direta.
FERRAMENTAS_DISPENSAVEIS = (
    "Bash",
    "Write",
    "Edit",
    "NotebookEdit",
    "WebFetch",
    "WebSearch",
    "Task",
    "Agent",
    "TodoWrite",
    "SlashCommand",
)

INSTRUCAO_INSTALACAO = (
    "A CLI do Claude Code nao foi encontrada. Instale e faca login uma vez:\n"
    "  npm install -g @anthropic-ai/claude-code\n"
    "  claude\n"
    "Se ela estiver instalada fora do PATH, aponte o caminho em CLAUDE_CLI no .env."
)


def localizar_cli(caminho_configurado: str = "") -> str | None:
    if caminho_configurado:
        return caminho_configurado if Path(caminho_configurado).exists() else None
    # `which` respeita PATHEXT no Windows, entao acha o claude.cmd do npm.
    return shutil.which("claude")


def _prompt(artigo: dict[str, Any], perguntas: list[dict[str, Any]], pdf: Path) -> str:
    linhas = [
        "Voce esta extraindo dados de um artigo cientifico para a revisao",
        "bibliografica sistematica de um mestrado sobre video imersivo e",
        "volumetrico, streaming e Head Mounted Displays (HMD).",
        "",
        f"Leia o PDF em: {pdf}",
        "(Se ele tiver mais de 20 paginas, leia em partes ate cobrir o artigo",
        "inteiro antes de responder.)",
        "",
        f"Titulo: {artigo['titulo']}",
    ]
    if artigo.get("ano"):
        linhas.append(f"Ano: {artigo['ano']}")
    if artigo.get("venue"):
        linhas.append(f"Veiculo: {artigo['venue']}")

    linhas += [
        "",
        "Responda estas perguntas de pesquisa:",
    ]
    for p in perguntas:
        linhas.append(f"  [id {p['id']}] {p['texto']}")

    linhas += [
        "",
        "Regras que nao podem ser quebradas:",
        "1. Responda SOMENTE com o que esta escrito no PDF. Nao complete com",
        "   conhecimento geral da area nem infira o que o artigo 'provavelmente' faz.",
        "2. Se o artigo nao trata do que a pergunta pede, diga isso e marque",
        "   confianca como 'nao_encontrado'. Um 'nao aborda' correto vale mais",
        "   que um palpite plausivel: e ele que revela lacuna na literatura.",
        "3. Seja especifico: numeros, nomes de datasets, modelos de HMD, metricas",
        "   e protocolos exatamente como aparecem no texto.",
        "4. `evidencia` deve ser um trecho VERBATIM do PDF, copiado sem reescrita.",
        "   String vazia se nao houver.",
        "5. Respostas em portugues do Brasil; a evidencia fica no idioma original.",
        "6. Conciso: 1 a 4 frases por resposta.",
        "",
        f"Devolva exatamente {len(perguntas)} respostas, uma por pergunta,",
        "usando os ids acima.",
    ]
    return "\n".join(linhas)


def rodar(
    prompt: str,
    cli: str,
    timeout_s: int,
    esquema: dict[str, Any] | None = None,
    modelo: str = "",
    ferramentas: tuple[str, ...] = (),
    diretorios: tuple[Path, ...] = (),
) -> tuple[str, dict[str, Any] | None, dict[str, Any]]:
    """Executa um prompt na CLI e devolve (texto, estruturado, metadados).

    `esquema` liga a saida estruturada (`--json-schema`); sem ele volta so o
    texto. `ferramentas` lista o que a sessao pode usar - vazio significa que
    tudo o que ela precisa ja esta no prompt, e ai nem o Read e liberado.

    `metadados` traz custo estimado e uso, que a CLI reporta por invocacao.
    """
    # O prompt vai por STDIN, nao como argumento de `-p`.
    #
    # No Windows a CLI e um `claude.CMD`, e o cmd.exe TRUNCA um argumento na
    # primeira quebra de linha. Medido nesta maquina: com o prompt em argv, a
    # sessao recebia so a primeira linha, ignorava o PDF e as perguntas, e
    # respondia conversando sobre o que achava que tinha sido perguntado.
    # Pelo stdin o texto chega inteiro, com `-p` sem argumento.
    comando = [
        cli,
        "-p",
        "--output-format",
        "json",
        # Nega o que nao estiver liberado em vez de perguntar - numa sessao
        # sem terminal, um prompt de permissao trava ate o timeout.
        "--permission-mode",
        "dontAsk",
        # Remove as ferramentas que nao servem aqui. Nao e so higiene: medido
        # nesta maquina, a definicao delas custava 13k tokens de entrada por
        # analise (42k -> 29k), e essa conta sai da sua franquia do Pro.
        "--disallowedTools",
        *FERRAMENTAS_DISPENSAVEIS,
        # Ignora os servidores MCP do ambiente. Sem isto, o resultado dependeria
        # de quais servidores estao configurados na maquina, e um servidor lento
        # atrasaria a partida de toda analise.
        "--strict-mcp-config",
        "--mcp-config",
        '{"mcpServers":{}}',
    ]
    if esquema is not None:
        comando += ["--json-schema", json.dumps(esquema)]
    if ferramentas:
        comando += ["--allowedTools", ",".join(ferramentas)]
    # Como a sessao roda fora do projeto, o que ela precisa ler tem que ser
    # liberado explicitamente.
    for diretorio in diretorios:
        comando += ["--add-dir", str(diretorio)]
    if modelo:
        comando += ["--model", modelo]

    PASTA_SESSAO.mkdir(parents=True, exist_ok=True)
    LOG.info("Invocando Claude Code (%s chars de prompt)", len(prompt))
    try:
        processo = subprocess.run(
            comando,
            input=prompt,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_s,
            cwd=str(PASTA_SESSAO),
        )
    except FileNotFoundError as exc:
        raise RuntimeError(INSTRUCAO_INSTALACAO) from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            f"A analise passou de {timeout_s // 60} minutos e foi interrompida. "
            "Artigos muito longos podem precisar de mais tempo: aumente "
            "TIMEOUT_ANALISE_S no .env."
        ) from exc

    if processo.returncode != 0:
        detalhe = (processo.stderr or processo.stdout or "").strip()[:400]
        raise RuntimeError(
            f"A CLI do Claude Code saiu com codigo {processo.returncode}. {detalhe}"
        )

    try:
        payload = json.loads(processo.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "Nao consegui ler a saida da CLI como JSON. "
            f"Comeco da saida: {processo.stdout[:200]!r}"
        ) from exc

    # Falha dentro da execucao (ex.: sem autenticacao) sai com codigo 0 e o
    # erro no proprio resultado - por isso a checagem depois do returncode.
    if payload.get("is_error"):
        raise RuntimeError(
            f"O Claude Code reportou erro: {str(payload.get('result'))[:300]}"
        )

    estruturado = payload.get("structured_output")
    if esquema is not None and not isinstance(estruturado, dict):
        raise RuntimeError(
            "A CLI nao devolveu a saida estruturada esperada. "
            f"Resultado em texto: {str(payload.get('result'))[:200]}"
        )

    uso = payload.get("usage") or {}
    # `input_tokens` conta so o que nao veio do cache; somar as tres parcelas
    # e o unico jeito de saber quanto contexto a invocacao realmente consumiu.
    entrada = (
        int(uso.get("input_tokens") or 0)
        + int(uso.get("cache_read_input_tokens") or 0)
        + int(uso.get("cache_creation_input_tokens") or 0)
    )
    metadados = {
        "custo_usd": float(payload.get("total_cost_usd") or 0.0),
        "tokens_entrada": entrada,
        "tokens_saida": int(uso.get("output_tokens") or 0),
        "sessao": payload.get("session_id"),
    }
    return str(payload.get("result") or ""), estruturado, metadados


def analisar(
    artigo: dict[str, Any],
    perguntas: list[dict[str, Any]],
    caminho_pdf: Path,
    esquema: dict[str, Any],
    cli: str,
    timeout_s: int,
    modelo: str = "",
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Le o PDF e responde as perguntas de pesquisa daquele artigo."""
    _texto, estruturado, metadados = rodar(
        prompt=_prompt(artigo, perguntas, caminho_pdf),
        cli=cli,
        timeout_s=timeout_s,
        esquema=esquema,
        modelo=modelo,
        # Ler o PDF e a unica coisa que ela precisa fazer.
        ferramentas=("Read",),
        diretorios=(caminho_pdf.parent,),
    )
    if not estruturado or "respostas" not in estruturado:
        raise RuntimeError("A CLI nao devolveu a lista de respostas esperada.")
    return estruturado["respostas"], metadados
