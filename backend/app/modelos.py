"""Modelos do SQLite.

Duas tabelas por enquanto: uma execucao de busca e os artigos que ela trouxe.
As tabelas de perguntas e respostas entram nas etapas seguintes.
"""

from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def agora() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class StatusPDF(str, enum.Enum):
    """Estado da aquisicao do full-text.

    `landing` existe por causa de um achado da Etapa 0: o Unpaywall costuma
    devolver a pagina do artigo em vez do arquivo. Isso nao e um PDF baixado
    nem e paywall - e um link que ainda precisa de intervencao, e misturar
    esse caso com "baixado" foi o que inflou a taxa no diagnostico inicial.
    """

    PENDENTE = "pendente"
    BAIXADO = "baixado"
    PAYWALL = "paywall"
    LANDING = "landing"
    ERRO = "erro"


class StatusBusca(str, enum.Enum):
    CONCLUIDA = "concluida"
    BAIXANDO = "baixando"
    ERRO = "erro"


class Busca(Base):
    __tablename__ = "buscas"

    id: Mapped[int] = mapped_column(primary_key=True)
    query: Mapped[str] = mapped_column(Text)
    total_scopus: Mapped[int] = mapped_column(Integer, default=0)
    recuperados: Mapped[int] = mapped_column(Integer, default=0)
    novos: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default=StatusBusca.CONCLUIDA.value)
    # Caminho do JSON bruto devolvido pela Scopus, relativo a raiz do projeto.
    arquivo_bruto: Mapped[str | None] = mapped_column(String(255), nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=agora)

    artigos: Mapped[list["Artigo"]] = relationship(
        back_populates="busca", cascade="all, delete-orphan"
    )


class Artigo(Base):
    __tablename__ = "artigos"
    # Um mesmo artigo pode aparecer em buscas diferentes; o par (busca, doi)
    # e que precisa ser unico. DOI vazio nao colide porque NULL != NULL.
    __table_args__ = (UniqueConstraint("busca_id", "doi", name="uq_busca_doi"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    busca_id: Mapped[int] = mapped_column(ForeignKey("buscas.id"), index=True)

    scopus_id: Mapped[str | None] = mapped_column(String(40), index=True)
    doi: Mapped[str | None] = mapped_column(String(200), index=True)
    titulo: Mapped[str] = mapped_column(Text)
    autores: Mapped[list | None] = mapped_column(JSON, default=list)
    ano: Mapped[int | None] = mapped_column(Integer, index=True)
    venue: Mapped[str | None] = mapped_column(Text)
    abstract: Mapped[str | None] = mapped_column(Text)
    keywords: Mapped[list | None] = mapped_column(JSON, default=list)
    citacoes: Mapped[int | None] = mapped_column(Integer)
    tipo: Mapped[str | None] = mapped_column(String(60))

    # --- Aquisicao do PDF ------------------------------------------------
    baixado: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    pdf_status: Mapped[str] = mapped_column(
        String(20), default=StatusPDF.PENDENTE.value, index=True
    )
    pdf_caminho: Mapped[str | None] = mapped_column(String(400))
    pdf_fonte: Mapped[str | None] = mapped_column(String(40))
    pdf_url: Mapped[str | None] = mapped_column(Text)
    pdf_bytes: Mapped[int | None] = mapped_column(Integer)
    pdf_detalhe: Mapped[str | None] = mapped_column(Text)

    criado_em: Mapped[datetime] = mapped_column(DateTime, default=agora)

    busca: Mapped[Busca] = relationship(back_populates="artigos")

    respostas: Mapped[list["Resposta"]] = relationship(
        back_populates="artigo", cascade="all, delete-orphan"
    )

    @property
    def tem_paywall(self) -> bool:
        """O que a listagem mostra como 'paywall'.

        `landing` entra aqui porque, do ponto de vista de quem vai ler, o
        efeito e o mesmo: o PDF nao veio sozinho.
        """
        return self.pdf_status in (StatusPDF.PAYWALL.value, StatusPDF.LANDING.value)


class Pergunta(Base):
    """Pergunta de pesquisa da revisao.

    Global, nao por busca: a mesma bateria de perguntas se aplica a todo
    artigo que entrar no corpus, inclusive os de uma busca futura.
    """

    __tablename__ = "perguntas"

    id: Mapped[int] = mapped_column(primary_key=True)
    texto: Mapped[str] = mapped_column(Text)
    ordem: Mapped[int] = mapped_column(Integer, default=0, index=True)
    # Arquivar em vez de apagar: uma pergunta descartada no meio da revisao
    # levaria junto as respostas ja escritas para ela.
    ativa: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=agora)

    respostas: Mapped[list["Resposta"]] = relationship(
        back_populates="pergunta", cascade="all, delete-orphan"
    )


class Resposta(Base):
    """Resposta de um artigo a uma pergunta. Uma linha por par."""

    __tablename__ = "respostas"
    __table_args__ = (
        UniqueConstraint("artigo_id", "pergunta_id", name="uq_artigo_pergunta"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    artigo_id: Mapped[int] = mapped_column(
        ForeignKey("artigos.id", ondelete="CASCADE"), index=True
    )
    pergunta_id: Mapped[int] = mapped_column(
        ForeignKey("perguntas.id", ondelete="CASCADE"), index=True
    )
    texto: Mapped[str] = mapped_column(Text, default="")
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime, default=agora, onupdate=agora
    )

    artigo: Mapped[Artigo] = relationship(back_populates="respostas")
    pergunta: Mapped[Pergunta] = relationship(back_populates="respostas")
