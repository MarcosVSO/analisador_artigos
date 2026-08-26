import { Link } from "react-router-dom";

import { urlPdf } from "../api";
import type { Artigo, PaginaArtigos } from "../tipos";
import { ETIQUETAS, formatarAutores, formatarTamanho } from "./etiquetas";

interface Props {
  pagina: PaginaArtigos | null;
  carregando: boolean;
  baixandoIds: Set<number>;
  anexandoIds: Set<number>;
  onDetalhar: (artigo: Artigo) => void;
  onBaixarArtigo: (artigo: Artigo) => void;
  onAnexarPdf: (artigo: Artigo, arquivo: File) => void;
  onMudarPagina: (pagina: number) => void;
}

interface PropsAnexar {
  artigo: Artigo;
  anexando: boolean;
  onAnexar: (artigo: Artigo, arquivo: File) => void;
}

/** Botao de anexar PDF do computador.
 *
 *  E um <label> com <input type="file"> escondido dentro em vez de um
 *  <button> + ref: clicar no label ja abre o seletor do sistema, sem JS.
 */
function BotaoAnexar({ artigo, anexando, onAnexar }: PropsAnexar) {
  const substituir = artigo.baixado;
  return (
    <label
      className={substituir ? "botao-icone anexar" : "botao-compacto anexar"}
      title={
        substituir
          ? "Substituir por outro PDF do computador"
          : "Selecionar o PDF deste artigo no computador"
      }
      aria-disabled={anexando}
    >
      {anexando ? (
        <>
          <span className="girando" />
          {substituir ? "" : "Enviando"}
        </>
      ) : substituir ? (
        "📎"
      ) : (
        "Anexar PDF"
      )}
      <input
        type="file"
        accept="application/pdf,.pdf"
        disabled={anexando}
        onChange={(e) => {
          const arquivo = e.target.files?.[0];
          // Zerar o value permite escolher o MESMO arquivo de novo depois de
          // um erro - sem isso o onChange nao dispara na segunda vez.
          e.target.value = "";
          if (arquivo) onAnexar(artigo, arquivo);
        }}
      />
    </label>
  );
}

export function TabelaArtigos({
  pagina,
  carregando,
  baixandoIds,
  anexandoIds,
  onDetalhar,
  onBaixarArtigo,
  onAnexarPdf,
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
              const anexando = anexandoIds.has(artigo.id);
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
                          <BotaoAnexar
                            artigo={artigo}
                            anexando={anexando}
                            onAnexar={onAnexarPdf}
                          />
                        </>
                      ) : (
                        <>
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
                          <BotaoAnexar
                            artigo={artigo}
                            anexando={anexando}
                            onAnexar={onAnexarPdf}
                          />
                        </>
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
