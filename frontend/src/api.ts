import type {
  Artigo,
  Busca,
  Configuracao,
  Filtros,
  Ordenacao,
  PaginaArtigos,
  PainelRespostas,
  Pergunta,
  ConsultaSintese,
  MatrizSintese,
  Progresso,
  RespostaAnalise,
  RespostaItem,
  ResumoRemocao,
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
  // Com FormData o Content-Type tem que ficar por conta do browser: e ele
  // que gera o `boundary` do multipart. Definir "application/json" aqui
  // deixaria o corpo ilegivel para o servidor.
  const ehFormulario = init?.body instanceof FormData;
  let resposta: Response;
  try {
    resposta = await fetch(url, {
      ...init,
      headers: ehFormulario
        ? init?.headers
        : { "Content-Type": "application/json", ...init?.headers },
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

  // 204 nao tem corpo para desserializar.
  if (resposta.status === 204) return undefined as T;
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

  obterBusca: (buscaId: number) => pedir<Busca>(`/api/buscas/${buscaId}`),

  /** Apaga a linha de pesquisa com seus artigos, respostas e PDFs. */
  removerBusca: (buscaId: number) =>
    pedir<ResumoRemocao>(`/api/buscas/${buscaId}`, { method: "DELETE" }),

  progresso: (buscaId: number) => pedir<Progresso>(`/api/buscas/${buscaId}/progresso`),

  /** `limite` ausente = todos os pendentes. */
  baixarPdfs: (buscaId: number, incluirFalhas = false, limite?: number) => {
    const params = new URLSearchParams({ incluir_falhas: String(incluirFalhas) });
    if (limite && limite > 0) params.set("limite", String(limite));
    return pedir<Progresso>(`/api/buscas/${buscaId}/baixar?${params}`, {
      method: "POST",
    });
  },

  baixarArtigo: (artigoId: number) =>
    pedir<Artigo>(`/api/artigos/${artigoId}/baixar`, { method: "POST" }),

  /** Vincula um PDF do seu computador ao artigo. */
  anexarPdf: (artigoId: number, arquivo: File) => {
    const corpo = new FormData();
    corpo.append("arquivo", arquivo);
    return pedir<Artigo>(`/api/artigos/${artigoId}/pdf`, {
      method: "POST",
      body: corpo,
    });
  },

  listarArtigos: (
    buscaId: number,
    filtros: Filtros,
    ordenarPor: Ordenacao,
    pagina: number,
  ) => {
    const params = new URLSearchParams({
      busca_id: String(buscaId),
      ordenar_por: ordenarPor,
      pagina: String(pagina),
      por_pagina: String(POR_PAGINA),
    });
    // Booleano so entra na URL quando o filtro esta ativo; ausente = "ambos".
    if (filtros.baixado !== null) params.set("baixado", String(filtros.baixado));
    if (filtros.paywall !== null) params.set("paywall", String(filtros.paywall));
    if (filtros.analisado !== null)
      params.set("analisado", String(filtros.analisado));
    if (filtros.texto.trim()) params.set("texto", filtros.texto.trim());
    return pedir<PaginaArtigos>(`/api/artigos?${params}`);
  },

  detalharArtigo: (artigoId: number) => pedir<Artigo>(`/api/artigos/${artigoId}`),

  // --- perguntas de pesquisa ---
  listarPerguntas: () => pedir<Pergunta[]>("/api/perguntas"),

  criarPergunta: (texto: string) =>
    pedir<Pergunta>("/api/perguntas", {
      method: "POST",
      body: JSON.stringify({ texto }),
    }),

  atualizarPergunta: (id: number, patch: Partial<Pick<Pergunta, "texto" | "ativa">>) =>
    pedir<Pergunta>(`/api/perguntas/${id}`, {
      method: "PATCH",
      body: JSON.stringify(patch),
    }),

  removerPergunta: (id: number) =>
    pedir<void>(`/api/perguntas/${id}`, { method: "DELETE" }),

  // --- respostas por artigo ---
  obterRespostas: (artigoId: number) =>
    pedir<PainelRespostas>(`/api/artigos/${artigoId}/respostas`),

  /** Analisa o PDF com o Claude. A resposta da IA e ACRESCENTADA ao que ja
   *  estiver escrito, nunca substitui. Demora ~1 min. */
  analisarComIA: (artigoId: number) =>
    pedir<RespostaAnalise>(`/api/artigos/${artigoId}/analisar`, { method: "POST" }),

  // --- sintese ---
  matriz: (buscaId: number | null, somenteAnalisados: boolean) => {
    const params = new URLSearchParams({
      somente_analisados: String(somenteAnalisados),
    });
    if (buscaId !== null) params.set("busca_id", String(buscaId));
    return pedir<MatrizSintese>(`/api/sintese?${params}`);
  },

  listarConsultas: (buscaId: number | null) => {
    const params = new URLSearchParams();
    if (buscaId !== null) params.set("busca_id", String(buscaId));
    return pedir<ConsultaSintese[]>(`/api/sintese/consultas?${params}`);
  },

  perguntarSintese: (
    pergunta: string,
    buscaId: number | null,
    somenteAnalisados: boolean,
  ) =>
    pedir<ConsultaSintese>("/api/sintese/consultas", {
      method: "POST",
      body: JSON.stringify({
        pergunta,
        busca_id: buscaId,
        somente_analisados: somenteAnalisados,
      }),
    }),

  removerConsulta: (id: number) =>
    pedir<void>(`/api/sintese/consultas/${id}`, { method: "DELETE" }),

  salvarResposta: (artigoId: number, perguntaId: number, texto: string) =>
    pedir<RespostaItem>(`/api/artigos/${artigoId}/respostas/${perguntaId}`, {
      method: "PUT",
      body: JSON.stringify({ texto }),
    }),
};

/** URL do CSV da matriz. Link direto, para o browser baixar o arquivo. */
export const urlCsvMatriz = (
  buscaId: number | null,
  somenteAnalisados: boolean,
) => {
  const params = new URLSearchParams({
    somente_analisados: String(somenteAnalisados),
  });
  if (buscaId !== null) params.set("busca_id", String(buscaId));
  return `/api/sintese/csv?${params}`;
};

/** URL do PDF servido pelo backend. `anexo` forca salvar em vez de abrir. */
export const urlPdf = (artigoId: number, anexo = false) =>
  `/api/artigos/${artigoId}/pdf${anexo ? "?anexo=true" : ""}`;
