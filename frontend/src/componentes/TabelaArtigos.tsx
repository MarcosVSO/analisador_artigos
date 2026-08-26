import { urlPdf } from "../api";
import type { Artigo, PaginaArtigos } from "../tipos";
import { ETIQUETAS, formatarAutores, formatarTamanho } from "./etiquetas";

interface Props {
  pagina: PaginaArtigos | null;
  carregando: boolean;
  onDetalhar: (artigo: Artigo) => void;
  onMudarPagina: (pagina: number) => void;
}

export function TabelaArtigos({
  pagina,
  carregando,
  onDetalhar,
  onMudarPagina,
}: Props) {
  if (carregando && !pagina) {
    return (
      <div className="cartao vazio">
        <span className="girando" /> Carregando artigos…
      </div>
    );
  }

  if (!pagina || !pagina.itens.length) {
    return (
      <div className="cartao vazio">
        Nenhum artigo para exibir. Rode uma busca ou ajuste os filtros.
      </div>
    );
  }

  const primeiro = (pagina.pagina - 1) * pagina.por_pagina + 1;
  const ultimo = primeiro + pagina.itens.length - 1;

  return (
    <div className="cartao">
      <div className="rolagem">
        <table>
          <thead>
            <tr>
              <th style={{ width: 40 }}></th>
              <th>Artigo</th>
              <th>Ano</th>
              <th className="num">Cit.</th>
              <th>PDF</th>
              <th>Fonte</th>
              <th>Ação</th>
            </tr>
          </thead>
          <tbody>
            {pagina.itens.map((artigo) => {
              const etiqueta = ETIQUETAS[artigo.pdf_status] ?? ETIQUETAS.pendente;
              return (
                <tr key={artigo.id}>
                  <td>
                    <button
                      className="lupa"
                      onClick={() => onDetalhar(artigo)}
                      title="Ver abstract, palavras-chave e detalhes"
                      aria-label={`Detalhes de ${artigo.titulo}`}
                    >
                      🔍
                    </button>
                  </td>
                  <td>
                    <div className="titulo-artigo">{artigo.titulo}</div>
                    <div className="meta">
                      {formatarAutores(artigo.autores)}
                      {artigo.venue && ` · ${artigo.venue}`}
                    </div>
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

      <div className="paginacao">
        <span className="meta">
          {primeiro}–{ultimo} de {pagina.total} artigos
          {carregando && <span className="girando" style={{ marginLeft: 8 }} />}
        </span>
        <div className="paginacao-botoes">
          <button
            onClick={() => onMudarPagina(pagina.pagina - 1)}
            disabled={pagina.pagina <= 1}
          >
            ← Anterior
          </button>
          <span className="meta">
            Página {pagina.pagina} de {pagina.paginas}
          </span>
          <button
            onClick={() => onMudarPagina(pagina.pagina + 1)}
            disabled={pagina.pagina >= pagina.paginas}
          >
            Próxima →
          </button>
        </div>
      </div>
    </div>
  );
}
