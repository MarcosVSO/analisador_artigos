"""Manutencao da flag `analisado` dos artigos.

Um artigo esta analisado quando TODAS as perguntas ativas tem resposta
preenchida. Como as perguntas sao globais, isso muda por dois caminhos:

- alguem escreveu (ou apagou) uma resposta -> muda um artigo;
- alguem criou, arquivou ou apagou uma pergunta -> muda TODOS os artigos.

O segundo caso e o que torna a flag traicoeira. Cadastrar a 9a pergunta faz
todo artigo que estava completo com 8 voltar a ficar incompleto, e uma flag
que nao acompanhasse isso mentiria justamente na hora de decidir o que ainda
falta ler. Por isso o recalculo vive aqui, num lugar so, e roda tambem na
subida do servidor - se algum caminho novo esquecer de chamar, o proximo
restart conserta.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

LOG = logging.getLogger(__name__)

# Quantas perguntas ativas existem hoje.
_ATIVAS = "(SELECT COUNT(*) FROM perguntas WHERE ativa = 1)"

# Quantas delas o artigo respondeu com texto de verdade. Uma linha vazia no
# banco nao e trabalho feito.
_RESPONDIDAS = """(
    SELECT COUNT(*)
    FROM respostas r
    JOIN perguntas p ON p.id = r.pergunta_id
    WHERE r.artigo_id = artigos.id
      AND p.ativa = 1
      AND TRIM(r.texto) <> ''
)"""

# `_ATIVAS > 0` evita o caso degenerado: sem nenhuma pergunta cadastrada,
# 0 >= 0 marcaria o corpus inteiro como analisado.
_COMPLETO = f"({_ATIVAS} > 0 AND {_RESPONDIDAS} >= {_ATIVAS})"

_ATUALIZAR = f"""
UPDATE artigos
SET analisado = CASE WHEN {_COMPLETO} THEN 1 ELSE 0 END,
    -- COALESCE preserva a data da primeira vez que ficou completo; voltar a
    -- ficar incompleto limpa, para nao sobrar carimbo de algo que nao vale.
    analisado_em = CASE WHEN {_COMPLETO} THEN COALESCE(analisado_em, :agora) END
"""


def recalcular_artigo(sessao: Session, artigo_id: int) -> bool:
    """Recalcula um artigo. Devolve o valor final da flag."""
    sessao.execute(
        text(_ATUALIZAR + " WHERE artigos.id = :artigo_id"),
        {"agora": datetime.now(timezone.utc), "artigo_id": artigo_id},
    )
    return bool(
        sessao.execute(
            text("SELECT analisado FROM artigos WHERE id = :artigo_id"),
            {"artigo_id": artigo_id},
        ).scalar()
    )


def recalcular_todos(sessao: Session) -> int:
    """Recalcula o corpus inteiro. Devolve quantos ficaram analisados.

    Uma unica UPDATE, entao roda em milissegundos mesmo com milhares de
    artigos - barato o bastante para chamar sempre que uma pergunta mudar.
    """
    sessao.execute(text(_ATUALIZAR), {"agora": datetime.now(timezone.utc)})
    total = sessao.execute(
        text("SELECT COUNT(*) FROM artigos WHERE analisado = 1")
    ).scalar()
    return int(total or 0)
