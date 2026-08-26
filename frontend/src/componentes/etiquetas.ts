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
  if (mb >= 1) return `${mb.toFixed(1)} MB`;
  const kb = bytes / 1024;
  // Arredondar direto mostraria "0 KB" para um arquivo pequeno, o que parece
  // arquivo vazio - e o sintoma exato de um upload que deu errado.
  return kb >= 1 ? `${Math.round(kb)} KB` : "<1 KB";
}

export function formatarAutores(autores: string[]): string {
  if (!autores.length) return "—";
  if (autores.length <= 2) return autores.join("; ");
  return `${autores[0]} et al.`;
}
