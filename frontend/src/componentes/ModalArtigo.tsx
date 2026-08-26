import { useEffect } from "react";

import { urlPdf } from "../api";
import type { Artigo } from "../tipos";
import { ETIQUETAS } from "./etiquetas";

interface Props {
  artigo: Artigo;
  onFechar: () => void;
}

export function ModalArtigo({ artigo, onFechar }: Props) {
  // Esc fecha. Sem isso o unico jeito de sair e mirar o X, o que incomoda
  // quando se abre um artigo atras do outro conferindo abstracts.
  useEffect(() => {
    function aoTeclar(evento: KeyboardEvent) {
      if (evento.key === "Escape") onFechar();
    }
    document.addEventListener("keydown", aoTeclar);
    return () => document.removeEventListener("keydown", aoTeclar);
  }, [onFechar]);

  const etiqueta = ETIQUETAS[artigo.pdf_status] ?? ETIQUETAS.pendente;

  return (
    <div className="fundo-modal" onClick={onFechar} role="presentation">
      <div
        className="modal"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label={artigo.titulo}
      >
        <div className="modal-cabecalho">
          <h2>{artigo.titulo}</h2>
          <button className="fechar" onClick={onFechar} aria-label="Fechar">
            ×
          </button>
        </div>

        <div className="modal-corpo">
          <dl className="ficha">
            <Campo rotulo="Autores" valor={artigo.autores.join("; ") || "—"} />
            <Campo rotulo="Ano" valor={artigo.ano ?? "—"} />
            <Campo rotulo="Veículo" valor={artigo.venue ?? "—"} />
            <Campo rotulo="Tipo" valor={artigo.tipo ?? "—"} />
            <Campo rotulo="Citações" valor={artigo.citacoes ?? 0} />
            <Campo
              rotulo="DOI"
              valor={
                artigo.doi ? (
                  <a
                    href={`https://doi.org/${artigo.doi}`}
                    target="_blank"
                    rel="noreferrer"
                  >
                    {artigo.doi}
                  </a>
                ) : (
                  "—"
                )
              }
            />
          </dl>

          <section>
            <h3>Abstract</h3>
            {artigo.abstract ? (
              <p className="abstract">{artigo.abstract}</p>
            ) : (
              <p className="meta">
                Não disponível. A busca do Scopus roda em <code>STANDARD</code>, e o
                OpenAlex não tinha o abstract deste DOI.
              </p>
            )}
          </section>

          <section>
            <h3>Palavras-chave</h3>
            {artigo.keywords.length ? (
              <div className="chips">
                {artigo.keywords.map((k) => (
                  <span className="chip" key={k}>
                    {k}
                  </span>
                ))}
              </div>
            ) : (
              <p className="meta">Nenhuma registrada.</p>
            )}
          </section>

          <section>
            <h3>Situação do PDF</h3>
            <p>
              <span className={`etiqueta ${etiqueta.classe}`}>{etiqueta.texto}</span>
              {artigo.pdf_fonte && <span className="meta"> · fonte: {artigo.pdf_fonte}</span>}
            </p>
            {artigo.pdf_detalhe && <p className="meta">{artigo.pdf_detalhe}</p>}
          </section>
        </div>

        <div className="modal-rodape">
          {artigo.baixado && (
            <a
              className="botao-pdf"
              href={urlPdf(artigo.id)}
              target="_blank"
              rel="noreferrer"
            >
              Abrir PDF
            </a>
          )}
          {!artigo.baixado && artigo.pdf_url && (
            <a
              className="botao-secundario"
              href={artigo.pdf_url}
              target="_blank"
              rel="noreferrer"
            >
              Ver página do artigo ↗
            </a>
          )}
          <button onClick={onFechar}>Fechar</button>
        </div>
      </div>
    </div>
  );
}

function Campo({ rotulo, valor }: { rotulo: string; valor: React.ReactNode }) {
  return (
    <>
      <dt>{rotulo}</dt>
      <dd>{valor}</dd>
    </>
  );
}
