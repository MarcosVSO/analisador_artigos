"""Aplicacao FastAPI do analisador de artigos."""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .banco import FabricaSessao, criar_tabelas
from .rotas import artigos, buscas, perguntas
from .servicos import estado_analise

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)

app = FastAPI(
    title="Analisador de Artigos",
    description="Busca no Scopus, aquisicao de PDFs e analise para revisao bibliografica.",
    version="0.1.0",
)

# O Vite serve o frontend em 5173 e faz proxy de /api. O CORS abaixo cobre o
# caso de abrir o frontend direto, sem o proxy.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(buscas.roteador)
app.include_router(artigos.roteador)
app.include_router(perguntas.roteador)


@app.on_event("startup")
def ao_iniciar() -> None:
    criar_tabelas()
    # Rede de seguranca: se algum caminho esquecer de recalcular a flag
    # `analisado`, a subida do servidor conserta.
    with FabricaSessao() as sessao:
        analisados = estado_analise.recalcular_todos(sessao)
        sessao.commit()
    logging.getLogger(__name__).info("Artigos analisados: %s", analisados)


@app.get("/api/saude")
def saude() -> dict[str, str]:
    return {"status": "ok"}
