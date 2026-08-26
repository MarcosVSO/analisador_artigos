import type { StatusPDF } from "../tipos";

/** Rotulo e cor de cada estado de aquisicao do PDF. Compartilhado entre a
 *  tabela e o modal para os dois nunca divergirem. */
export const ETIQUETAS: Record<
  StatusPDF,
  { texto: string; classe: string; ajuda: string }
> = {
  baixado: { texto: "Baixado", classe: "ok", ajuda: "PDF salvo em dados/pdfs" },
  paywall: {
    texto: "Paywall",
    classe: "atencao",
    ajuda: "Sem versão aberta — precisa de upload manual pelo acesso da universidade",
  },
  landing: {
    texto: "Paywall (só página)",
    classe: "atencao",
    ajuda: "Há versão aberta, mas só a página do artigo — sem link direto de PDF",
  },
  erro: {
    texto: "Falhou",
    classe: "erro",
    ajuda: "O link prometia PDF mas o download não completou",
  },
  pendente: { texto: "Pendente", classe: "neutro", ajuda: "Ainda não foi tentado" },
};

export function formatarTamanho(bytes: number | null): string {
  if (!bytes) return "";
  const mb = bytes / (1024 * 1024);
  return mb >= 1 ? `${mb.toFixed(1)} MB` : `${Math.round(bytes / 1024)} KB`;
}

export function formatarAutores(autores: string[]): string {
  if (!autores.length) return "—";
  if (autores.length <= 2) return autores.join("; ");
  return `${autores[0]} et al.`;
}
