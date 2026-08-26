import { urlPdf } from "../api";
import type { Artigo, StatusPDF } from "../tipos";

interface Props {
  artigos: Artigo[];
  carregando: boolean;
}

/** Rotulo e cor de cada estado de aquisicao do PDF. */
const ETIQUETAS: Record<StatusPDF, { texto: string; classe: string; ajuda: string }> = {
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

function formatarTamanho(bytes: number | null): string {
  if (!bytes) return "";
  const mb = bytes / (1024 * 1024);
  return mb >= 1 ? `${mb.toFixed(1)} MB` : `${Math.round(bytes / 1024)} KB`;
}

function formatarAutores(autores: string[]): string {
  if (!autores.length) return "—";
  if (autores.length <= 2) return autores.join("; ");
  return `${autores[0]} et al.`;
}

export function TabelaArtigos({ artigos, carregando }: Props) {
  if (carregando) {
    return (
      <div className="cartao vazio">
        <span className="girando" /> Carregando artigos…
      </div>
    );
  }

  if (!artigos.length) {
    return (
      <div className="cartao vazio">
        Nenhum artigo para exibir. Rode uma busca ou ajuste os filtros.
      </div>
    );
  }

  const baixados = artigos.filter((a) => a.baixado).length;

  return (
    <div className="cartao">
      <div className="rolagem">
        <table>
          <thead>
            <tr>
              <th style={{ width: "45%" }}>Artigo</th>
              <th>Ano</th>
              <th className="num">Cit.</th>
              <th>PDF</th>
              <th>Fonte</th>
              <th>Ação</th>
            </tr>
          </thead>
          <tbody>
            {artigos.map((artigo) => {
              const etiqueta = ETIQUETAS[artigo.pdf_status] ?? ETIQUETAS.pendente;
              return (
                <tr key={artigo.id}>
                  <td>
                    <div className="titulo-artigo">{artigo.titulo}</div>
                    <div className="meta">
                      {formatarAutores(artigo.autores)}
                      {artigo.venue && ` · ${artigo.venue}`}
                    </div>
                    {artigo.doi && <div className="meta">doi:{artigo.doi}</div>}
                  </td>
                  <td>{artigo.ano ?? "—"}</td>
                  <td className="num">{artigo.citacoes ?? 0}</td>
                  <td>
                    <span
                      className={`etiqueta ${etiqueta.classe}`}
                      title={artigo.pdf_detalhe || etiqueta.ajuda}
                    >
                      {etiqueta.texto}
                    </span>
                    {artigo.baixado && (
                      <div className="meta">{formatarTamanho(artigo.pdf_bytes)}</div>
                    )}
                  </td>
                  <td className="meta">{artigo.pdf_fonte ?? "—"}</td>
                  <td>
                    {artigo.baixado ? (
                      <a
                        className="botao-pdf"
                        href={urlPdf(artigo.id)}
                        target="_blank"
                        rel="noreferrer"
                      >
                        Abrir PDF
                      </a>
                    ) : artigo.pdf_url ? (
                      <a
                        className="meta"
                        href={artigo.pdf_url}
                        target="_blank"
                        rel="noreferrer"
                        title="Abre a página do artigo no site do editor"
                      >
                        Ver página ↗
                      </a>
                    ) : (
                      <span className="meta">—</span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <div className="rodape-tabela">
        {artigos.length} artigos · {baixados} com PDF disponível
      </div>
    </div>
  );
}
