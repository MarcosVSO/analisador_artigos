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
}

export interface Configuracao {
  query_padrao: string;
  credenciais_ok: boolean;
  aviso: string;
  view_scopus: string;
}

export type Situacao = "todos" | "baixados" | "sem_pdf";
