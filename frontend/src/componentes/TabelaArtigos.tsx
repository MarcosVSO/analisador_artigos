import { Link } from "react-router-dom";

import { urlPdf } from "../api";
import type { Artigo, PaginaArtigos } from "../tipos";
import { ETIQUETAS, formatarAutores, formatarTamanho } from "./etiquetas";

interface Props {
  pagina: PaginaArtigos | null;
  carregando: boolean;
  baixandoIds: Set<number>;
  onDetalhar: (artigo: Artigo) => void;
  onBaixarArtigo: (artigo: Artigo) => void;
  onMudarPagina: (pagina: number) => void;
}

export function TabelaArtigos({
  pagina,
  carregando,
  baixandoIds,
  onDetalhar,
  onBaixarArtigo,
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
              <th>Ações</th>
            </tr>
          </thead>
          <tbody>
            {pagina.itens.map((artigo) => {
              const etiqueta = ETIQUETAS[artigo.pdf_status] ?? ETIQUETAS.pendente;
              const baixando = baixandoIds.has(artigo.id);
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
                      <div className="meta">
                        {formatarTamanho(artigo.pdf_bytes)}
                        {artigo.pdf_fonte && ` · ${artigo.pdf_fonte}`}
                      </div>
                    )}
                  </td>
                  <td>
                    <div className="acoes-linha">
                      {artigo.baixado ? (
                        <>
                          <a
                            className="botao-pdf"
                            href={urlPdf(artigo.id)}
                            target="_blank"
                            rel="noreferrer"
                          >
                            Abrir PDF
                          </a>
                          <a
                            className="botao-icone"
                            href={urlPdf(artigo.id, true)}
                            title="Salvar o PDF no computador"
                            aria-label={`Salvar PDF de ${artigo.titulo}`}
                          >
                            ⬇
                          </a>
                        </>
                      ) : (
                        <button
                          className="botao-compacto"
                          onClick={() => onBaixarArtigo(artigo)}
                          disabled={baixando}
                          title="Tentar baixar o PDF deste artigo agora"
                        >
                          {baixando ? (
                            <>
                              <span className="girando" />
                              Baixando
                            </>
                          ) : (
                            "Baixar"
                          )}
                        </button>
                      )}
                      <Link
                        className="botao-compacto"
                        to={`/artigos/${artigo.id}/perguntas`}
                        title="Responder as perguntas de pesquisa deste artigo"
                      >
                        Perguntas
                      </Link>
                    </div>
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
