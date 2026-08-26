"""Engine e sessao do SQLite."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from .config import URL_BANCO
from .modelos import Base

engine = create_engine(
    URL_BANCO,
    # O download roda em thread de background e toca a mesma conexao.
    connect_args={"check_same_thread": False},
    future=True,
)


@event.listens_for(engine, "connect")
def _configurar_sqlite(conexao, _registro) -> None:
    cursor = conexao.cursor()
    # WAL deixa a API ler enquanto o download escreve, sem "database is locked".
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()


FabricaSessao = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def criar_tabelas() -> None:
    Base.metadata.create_all(engine)


def obter_sessao() -> Iterator[Session]:
    """Dependencia do FastAPI."""
    sessao = FabricaSessao()
    try:
        yield sessao
    finally:
        sessao.close()


@contextmanager
def sessao_escopo() -> Iterator[Session]:
    """Sessao para codigo fora do request (tarefas de background)."""
    sessao = FabricaSessao()
    try:
        yield sessao
        sessao.commit()
    except Exception:
        sessao.rollback()
        raise
    finally:
        sessao.close()
