import type { Artigo, Busca, Configuracao, Progresso, Situacao } from "./tipos";

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

export const api = {
  configuracao: () => pedir<Configuracao>("/api/configuracao"),

  criarBusca: (query: string, maxResultados: number) =>
    pedir<Busca>("/api/buscas", {
      method: "POST",
      body: JSON.stringify({
        query,
        max_resultados: maxResultados,
        baixar_automaticamente: true,
      }),
    }),

  listarBuscas: () => pedir<Busca[]>("/api/buscas"),

  progresso: (buscaId: number) => pedir<Progresso>(`/api/buscas/${buscaId}/progresso`),

  baixarPdfs: (buscaId: number) =>
    pedir<Progresso>(`/api/buscas/${buscaId}/baixar`, { method: "POST" }),

  listarArtigos: (buscaId: number, situacao: Situacao, texto: string) => {
    const params = new URLSearchParams({ busca_id: String(buscaId), situacao });
    if (texto.trim()) params.set("texto", texto.trim());
    return pedir<Artigo[]>(`/api/artigos?${params}`);
  },
};

/** URL do PDF servido pelo backend. Abre inline em nova aba. */
export const urlPdf = (artigoId: number) => `/api/artigos/${artigoId}/pdf`;
