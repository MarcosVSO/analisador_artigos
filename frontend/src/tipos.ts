export type StatusPDF = "pendente" | "baixado" | "paywall" | "landing" | "erro";

export interface Artigo {
  id: number;
  busca_id: number;
  doi: string | null;
  titulo: string;
  autores: string[];
  ano: number | null;
  venue: string | null;
  abstract: string | null;
  keywords: string[];
  citacoes: number | null;
  tipo: string | null;
  analisado: boolean;
  analisado_em: string | null;
  baixado: boolean;
  pdf_status: StatusPDF;
  pdf_fonte: string | null;
  pdf_url: string | null;
  pdf_bytes: number | null;
  pdf_detalhe: string | null;
  tem_paywall: boolean;
}

export interface Busca {
  id: number;
  query: string;
  total_scopus: number;
  recuperados: number;
  novos: number;
  status: string;
  arquivo_bruto: string | null;
  criado_em: string;
  artigos_total: number;
  artigos_baixados: number;
  respostas_escritas: number;
}

export interface ResumoRemocao {
  busca_id: number;
  artigos_removidos: number;
  pdfs_apagados: number;
  respostas_apagadas: number;
  arquivo_bruto_apagado: boolean;
}

export interface Progresso {
  busca_id: number;
  total: number;
  baixados: number;
  pendentes: number;
  paywall: number;
  landing: number;
  erro: number;
  em_andamento: boolean;
  a_baixar: number;
  analisados: number;
}

export interface PaginaArtigos {
  itens: Artigo[];
  total: number;
  pagina: number;
  por_pagina: number;
  paginas: number;
}

/** null = sem filtro (mostra os dois casos). */
export interface Filtros {
  texto: string;
  baixado: boolean | null;
  paywall: boolean | null;
  analisado: boolean | null;
}

export type Ordenacao = "citacoes" | "ano_desc" | "ano_asc" | "titulo";

export interface Pergunta {
  id: number;
  texto: string;
  ordem: number;
  ativa: boolean;
}

export interface RespostaItem {
  pergunta_id: number;
  pergunta_texto: string;
  ordem: number;
  texto: string;
}

export interface PainelRespostas {
  artigo: Artigo;
  itens: RespostaItem[];
  respondidas: number;
  analisado: boolean;
}

export interface ResumoAnalise {
  perguntas_respondidas: number;
  nao_encontrados: number;
  modelo: string;
  tokens_entrada: number;
  tokens_saida: number;
  custo_estimado_usd: number;
}

export interface RespostaAnalise {
  painel: PainelRespostas;
  resumo: ResumoAnalise;
}

export interface Configuracao {
  query_padrao: string;
  credenciais_ok: boolean;
  aviso: string;
  view_scopus: string;
  modo_analise: string;
  analise_pronta: boolean;
  analise_aviso: string;
}


// --- Síntese ---------------------------------------------------------------

export interface PerguntaMatriz {
  id: number;
  texto: string;
  ordem: number;
}

export interface LinhaMatriz {
  artigo_id: number;
  titulo: string;
  autores: string[];
  ano: number | null;
  venue: string | null;
  doi: string | null;
  analisado: boolean;
  /** pergunta_id -> texto da resposta */
  respostas: Record<number, string>;
}

export interface MatrizSintese {
  perguntas: PerguntaMatriz[];
  artigos: LinhaMatriz[];
  total: number;
}

export interface ConsultaSintese {
  id: number;
  busca_id: number | null;
  pergunta: string;
  resposta: string;
  artigos_considerados: number;
  modelo: string | null;
  custo_usd: number | null;
  criado_em: string;
}
