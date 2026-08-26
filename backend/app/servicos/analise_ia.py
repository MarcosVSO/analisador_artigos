"""Analise de um artigo pelo Claude, respondendo as perguntas de pesquisa.

Uma chamada por artigo, com todas as perguntas de uma vez: o PDF e o insumo
caro do request, e mandar um por pergunta o reenviaria N vezes.

A saida vem por tool use com `strict: True` em vez de texto livre. Parsear
texto para casar resposta com pergunta e fragil, e aqui um desalinhamento
colocaria a resposta da pergunta 3 no campo da 5 - o tipo de erro que passa
despercebido e contamina a matriz de sintese inteira.
"""

from __future__ import annotations

import base64
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import anthropic

from .. import config
from . import analise_claude_code

LOG = logging.getLogger(__name__)

# Limites da API para PDF em base64: 32 MB por request e 600 paginas. Fica
# um pouco abaixo porque o base64 infla o binario em ~33%.
MAX_BYTES_PDF = 22 * 1024 * 1024

PRECO_ENTRADA_POR_MILHAO = 5.0
PRECO_SAIDA_POR_MILHAO = 25.0

PROMPT_SISTEMA = """\
Voce esta ajudando um pesquisador de mestrado a extrair dados de artigos \
cientificos para uma revisao bibliografica sistematica sobre video imersivo \
e volumetrico, streaming e Head Mounted Displays (HMD).

Regras que nao podem ser quebradas:

1. Responda SOMENTE com o que esta escrito no PDF anexado. Nao complete com \
conhecimento geral da area, nao infira o que o artigo "provavelmente" faz.
2. Se o artigo nao trata do que a pergunta pede, responda exatamente que o \
artigo nao aborda isso e marque a confianca como "nao_encontrado". Um \
"nao aborda" correto vale mais que um palpite plausivel: o pesquisador vai \
usar isso para identificar lacunas na literatura.
3. Seja especifico. Cite numeros, nomes de datasets, modelos de HMD, metricas \
e nomes de protocolos exatamente como aparecem no texto.
4. O campo `evidencia` deve ser um trecho VERBATIM do PDF que sustenta a \
resposta, copiado sem reescrita. Se nao houver trecho, deixe vazio.
5. Escreva as respostas em portugues do Brasil, mesmo que o artigo esteja em \
ingles. A `evidencia` fica no idioma original do artigo.
6. Seja conciso: 1 a 4 frases por resposta.
"""

FERRAMENTA = {
    "name": "registrar_respostas",
    "description": (
        "Registra a resposta para cada pergunta de pesquisa. Deve conter "
        "exatamente uma entrada por pergunta recebida, usando o mesmo "
        "pergunta_id."
    ),
    "strict": True,
    "input_schema": {
        "type": "object",
        "properties": {
            "respostas": {
                "type": "array",
                "description": "Uma entrada por pergunta, na mesma ordem recebida.",
                "items": {
                    "type": "object",
                    "properties": {
                        "pergunta_id": {
                            "type": "integer",
                            "description": "O id exato da pergunta respondida.",
                        },
                        "resposta": {
                            "type": "string",
                            "description": "Resposta em portugues, 1 a 4 frases.",
                        },
                        "evidencia": {
                            "type": "string",
                            "description": (
                                "Trecho verbatim do PDF que sustenta a resposta. "
                                "String vazia se nao houver."
                            ),
                        },
                        "pagina": {
                            "type": "integer",
                            "description": "Pagina do trecho. 0 se nao identificavel.",
                        },
                        "confianca": {
                            "type": "string",
                            "enum": ["alta", "media", "baixa", "nao_encontrado"],
                        },
                    },
                    "required": [
                        "pergunta_id",
                        "resposta",
                        "evidencia",
                        "pagina",
                        "confianca",
                    ],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["respostas"],
        "additionalProperties": False,
    },
}


# O mesmo esquema serve aos dois modos: input_schema da ferramenta na API,
# e --json-schema na CLI.
ESQUEMA_RESPOSTAS = FERRAMENTA["input_schema"]


class AnaliseError(Exception):
    """Falha que o usuario precisa ver no frontend."""


@dataclass
class RespostaIA:
    pergunta_id: int
    resposta: str
    evidencia: str
    pagina: int
    confianca: str


@dataclass
class ResultadoAnalise:
    respostas: list[RespostaIA]
    tokens_entrada: int
    tokens_saida: int
    modelo: str
    # A CLI ja reporta o custo da invocacao; a API nao, entao ali fica None e
    # o valor sai da conta por token.
    custo_informado: float | None = None

    @property
    def custo_estimado(self) -> float:
        if self.custo_informado is not None:
            return self.custo_informado
        return (
            self.tokens_entrada / 1_000_000 * PRECO_ENTRADA_POR_MILHAO
            + self.tokens_saida / 1_000_000 * PRECO_SAIDA_POR_MILHAO
        )


SEM_CREDENCIAL = (
    "Nenhuma credencial da Anthropic encontrada. Defina ANTHROPIC_API_KEY no "
    ".env (crie a chave em https://console.anthropic.com/settings/keys) e "
    "reinicie o backend."
)


def _cliente() -> anthropic.Anthropic:
    """Construtor sem argumentos: o SDK resolve ANTHROPIC_API_KEY,
    ANTHROPIC_AUTH_TOKEN ou um perfil do `ant auth login`, nessa ordem.

    Nao da para validar a credencial aqui: sem chave nenhuma o construtor
    passa limpo e so o primeiro request levanta TypeError. Por isso quem
    chama tambem precisa tratar esse caso.
    """
    return anthropic.Anthropic()


def _ler_pdf(caminho: Path) -> str:
    if not caminho.exists():
        raise AnaliseError(
            "O PDF deste artigo nao esta no disco. Baixe ou anexe o arquivo antes."
        )
    dados = caminho.read_bytes()
    if len(dados) > MAX_BYTES_PDF:
        raise AnaliseError(
            f"O PDF tem {len(dados) / (1024 * 1024):.0f} MB e passa do limite de "
            f"{MAX_BYTES_PDF // (1024 * 1024)} MB da API. Reduza o arquivo "
            "(por exemplo, comprimindo as imagens) e tente de novo."
        )
    return base64.standard_b64encode(dados).decode("ascii")


def _montar_pedido(artigo: dict[str, Any], perguntas: list[dict[str, Any]]) -> str:
    linhas = [
        "Artigo a analisar (PDF anexado):",
        f"  Titulo: {artigo['titulo']}",
    ]
    if artigo.get("ano"):
        linhas.append(f"  Ano: {artigo['ano']}")
    if artigo.get("venue"):
        linhas.append(f"  Veiculo: {artigo['venue']}")
    if artigo.get("doi"):
        linhas.append(f"  DOI: {artigo['doi']}")

    linhas.append("")
    linhas.append("Perguntas de pesquisa a responder:")
    for p in perguntas:
        linhas.append(f"  [id {p['id']}] {p['texto']}")

    linhas.append("")
    linhas.append(
        "Chame a ferramenta registrar_respostas com exatamente "
        f"{len(perguntas)} entradas, uma por pergunta, usando os ids acima."
    )
    return "\n".join(linhas)


def analisar(
    artigo: dict[str, Any],
    perguntas: list[dict[str, Any]],
    caminho_pdf: Path,
) -> ResultadoAnalise:
    """Ponto de entrada. Escolhe o executor conforme config.MODO_ANALISE."""
    if not perguntas:
        raise AnaliseError(
            "Nenhuma pergunta de pesquisa cadastrada. Crie as suas pelo botao "
            '"Perguntas de pesquisa" na listagem.'
        )
    if not caminho_pdf.exists():
        raise AnaliseError(
            "O PDF deste artigo nao esta no disco. Baixe ou anexe o arquivo antes."
        )

    if config.MODO_ANALISE == "claude_code":
        return _analisar_via_claude_code(artigo, perguntas, caminho_pdf)
    return _analisar_via_api(artigo, perguntas, caminho_pdf)


def _normalizar(
    bruto: list[dict[str, Any]], perguntas: list[dict[str, Any]]
) -> list[RespostaIA]:
    ids_validos = {p["id"] for p in perguntas}
    return [
        RespostaIA(
            pergunta_id=int(r["pergunta_id"]),
            resposta=(r.get("resposta") or "").strip(),
            evidencia=(r.get("evidencia") or "").strip(),
            pagina=int(r.get("pagina") or 0),
            confianca=r.get("confianca") or "baixa",
        )
        for r in bruto
        # Um id inventado gravaria resposta na pergunta errada; descartar e
        # melhor do que gravar torto.
        if int(r.get("pergunta_id", -1)) in ids_validos
    ]


def _analisar_via_claude_code(
    artigo: dict[str, Any],
    perguntas: list[dict[str, Any]],
    caminho_pdf: Path,
) -> ResultadoAnalise:
    cli = analise_claude_code.localizar_cli(config.CLAUDE_CLI)
    if cli is None:
        raise AnaliseError(analise_claude_code.INSTRUCAO_INSTALACAO)

    try:
        bruto, meta = analise_claude_code.analisar(
            artigo=artigo,
            perguntas=perguntas,
            caminho_pdf=caminho_pdf,
            esquema=ESQUEMA_RESPOSTAS,
            cli=cli,
            timeout_s=config.TIMEOUT_ANALISE_S,
            modelo=config.MODELO_ANALISE_CLI,
        )
    except RuntimeError as exc:
        raise AnaliseError(str(exc)) from exc

    respostas = _normalizar(bruto, perguntas)
    if not respostas:
        raise AnaliseError("O Claude Code nao devolveu nenhuma resposta valida.")

    return ResultadoAnalise(
        respostas=respostas,
        tokens_entrada=meta["tokens_entrada"],
        tokens_saida=meta["tokens_saida"],
        modelo="Claude Code (assinatura)",
        custo_informado=meta["custo_usd"],
    )


def _analisar_via_api(
    artigo: dict[str, Any],
    perguntas: list[dict[str, Any]],
    caminho_pdf: Path,
) -> ResultadoAnalise:
    pdf_b64 = _ler_pdf(caminho_pdf)
    cliente = _cliente()

    conteudo = [
        {
            "type": "document",
            "source": {
                "type": "base64",
                "media_type": "application/pdf",
                "data": pdf_b64,
            },
        },
        {"type": "text", "text": _montar_pedido(artigo, perguntas)},
    ]

    try:
        # Streaming porque o PDF inteiro no input mais o thinking podem passar
        # do timeout HTTP de um request nao-streamado.
        with cliente.beta.messages.stream(
            model=config.MODELO_ANALISE,
            max_tokens=16000,
            system=PROMPT_SISTEMA,
            messages=[{"role": "user", "content": conteudo}],
            tools=[FERRAMENTA],
            tool_choice={"type": "tool", "name": "registrar_respostas"},
            thinking={"type": "adaptive"},
            # Se um classificador recusar o pedido, a API roteia para outro
            # modelo em vez de devolver a analise vazia.
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        ) as fluxo:
            mensagem = fluxo.get_final_message()
    except TypeError as exc:
        # Sem nenhuma credencial resolvivel, o SDK levanta TypeError na hora
        # de montar os headers - nao uma excecao da familia AuthenticationError.
        if "authentication" in str(exc).lower():
            raise AnaliseError(SEM_CREDENCIAL) from exc
        raise
    except anthropic.AuthenticationError as exc:
        raise AnaliseError(
            "A Anthropic recusou a credencial. Confira ANTHROPIC_API_KEY no .env."
        ) from exc
    except anthropic.RateLimitError as exc:
        raise AnaliseError(
            "Limite de requisicoes da Anthropic atingido. Espere um pouco e "
            "tente de novo."
        ) from exc
    except anthropic.APIStatusError as exc:
        raise AnaliseError(f"A API da Anthropic respondeu {exc.status_code}.") from exc
    except anthropic.APIConnectionError as exc:
        raise AnaliseError("Nao consegui falar com a API da Anthropic.") from exc

    # `stop_details` so vem preenchido em recusa; checar antes de ler content.
    if mensagem.stop_reason == "refusal":
        raise AnaliseError(
            "O modelo recusou analisar este PDF. Isso costuma indicar um "
            "arquivo corrompido ou que nao e o artigo esperado."
        )

    bruto: list[dict[str, Any]] = []
    for bloco in mensagem.content:
        if bloco.type == "tool_use" and bloco.name == "registrar_respostas":
            # Nunca casar string na entrada serializada: o escape de JSON
            # varia entre modelos. O SDK ja entrega dict aqui.
            bruto = bloco.input.get("respostas", [])
            break

    if not bruto:
        raise AnaliseError(
            "O modelo nao devolveu respostas estruturadas. Tente novamente."
        )

    return ResultadoAnalise(
        respostas=_normalizar(bruto, perguntas),
        tokens_entrada=mensagem.usage.input_tokens,
        tokens_saida=mensagem.usage.output_tokens,
        modelo=config.MODELO_ANALISE,
    )


def compor_texto(existente: str, ia: RespostaIA) -> str:
    """Junta a resposta da IA ao que ja estava escrito, sem substituir nada.

    O bloco da IA vai DEPOIS do texto humano e sempre marcado com "I.A:",
    para que dentro de seis meses continue obvio o que voce escreveu e o que
    a maquina sugeriu - distincao que a banca vai cobrar.
    """
    linhas = [f"I.A: {ia.resposta}"]
    if ia.evidencia:
        pagina = f" (p. {ia.pagina})" if ia.pagina else ""
        linhas.append(f'Evidência: "{ia.evidencia}"{pagina}')
    if ia.confianca == "nao_encontrado":
        linhas.append("Confiança: o artigo não aborda este ponto.")
    elif ia.confianca in ("baixa", "media"):
        linhas.append(f"Confiança: {ia.confianca}.")

    bloco = "\n".join(linhas)
    if existente.strip():
        return f"{existente.rstrip()}\n\n{bloco}"
    return bloco
