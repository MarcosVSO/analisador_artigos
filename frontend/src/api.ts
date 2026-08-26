import type {
  Artigo,
  Busca,
  Configuracao,
  Filtros,
  PaginaArtigos,
  Progresso,
} from "./tipos";

/** Erro da API com a mensagem que o backend mandou, nao um "Failed to fetch". */
export class ErroApi extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message);
    this.name = "ErroApi";
  }
}

async function pedir<T>(url: string, init?: RequestInit): Promise<T> {
  let resposta: Response;
  try {
    resposta = await fetch(url, {
      headers: { "Content-Type": "application/json" },
      ...init,
    });
  } catch {
    throw new ErroApi(
      "Nao consegui falar com o backend. Ele esta rodando em localhost:8000?",
      0,
    );
  }

  if (!resposta.ok) {
    // O FastAPI devolve o motivo em `detail`; e ele que o usuario precisa ler.
    let detalhe = `Erro ${resposta.status}`;
    try {
      const corpo = await resposta.json();
      if (typeof corpo?.detail === "string") detalhe = corpo.detail;
      else if (Array.isArray(corpo?.detail)) detalhe = corpo.detail[0]?.msg ?? detalhe;
    } catch {
      /* resposta sem JSON: fica a mensagem generica */
    }
    throw new ErroApi(detalhe, resposta.status);
  }

  return resposta.json() as Promise<T>;
}

export const POR_PAGINA = 15;

export const api = {
  configuracao: () => pedir<Configuracao>("/api/configuracao"),

  /** Busca no Scopus. Traz todos os resultados e nao dispara download. */
  criarBusca: (query: string) =>
    pedir<Busca>("/api/buscas", {
      method: "POST",
      body: JSON.stringify({ query }),
    }),

  listarBuscas: () => pedir<Busca[]>("/api/buscas"),

  progresso: (buscaId: number) => pedir<Progresso>(`/api/buscas/${buscaId}/progresso`),

  baixarPdfs: (buscaId: number, incluirFalhas = false) =>
    pedir<Progresso>(
      `/api/buscas/${buscaId}/baixar?incluir_falhas=${incluirFalhas}`,
      { method: "POST" },
    ),

  listarArtigos: (buscaId: number, filtros: Filtros, pagina: number) => {
    const params = new URLSearchParams({
      busca_id: String(buscaId),
      pagina: String(pagina),
      por_pagina: String(POR_PAGINA),
    });
    // Booleano so entra na URL quando o filtro esta ativo; ausente = "ambos".
    if (filtros.baixado !== null) params.set("baixado", String(filtros.baixado));
    if (filtros.paywall !== null) params.set("paywall", String(filtros.paywall));
    if (filtros.texto.trim()) params.set("texto", filtros.texto.trim());
    return pedir<PaginaArtigos>(`/api/artigos?${params}`);
  },

  detalharArtigo: (artigoId: number) => pedir<Artigo>(`/api/artigos/${artigoId}`),
};

/** URL do PDF servido pelo backend. Abre inline em nova aba. */
export const urlPdf = (artigoId: number) => `/api/artigos/${artigoId}/pdf`;
