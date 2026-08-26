import { useState } from "react";

import type { Busca } from "../tipos";

interface Props {
  buscas: Busca[];
  ativa: Busca | null;
  removendoId: number | null;
  onSelecionar: (busca: Busca) => void;
  onRemover: (busca: Busca) => void;
}

function formatarData(iso: string): string {
  // O backend grava em UTC sem sufixo; sem o "Z" o browser leria como local.
  const d = new Date(iso.endsWith("Z") ? iso : `${iso}Z`);
  return d.toLocaleString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function ListaBuscas({
  buscas,
  ativa,
  removendoId,
  onSelecionar,
  onRemover,
}: Props) {
  // Com uma linha só, a lista não acrescenta nada; abre fechada e só cresce
  // quando há de fato entre o que escolher.
  const [expandida, setExpandida] = useState(false);

  if (!buscas.length) return null;

  const visiveis = expandida ? buscas : buscas.filter((b) => b.id === ativa?.id);

  return (
    <div className="cartao">
      <div className="painel-topo" style={{ marginBottom: 12 }}>
        <div>
          <strong>Linhas de pesquisa ({buscas.length})</strong>
          <div className="meta">
            Cada busca no Scopus cria uma linha nova. As anteriores continuam
            aqui, com os PDFs e as respostas delas.
          </div>
        </div>
        {buscas.length > 1 && (
          <button onClick={() => setExpandida((v) => !v)}>
            {expandida ? "Recolher" : `Ver todas (${buscas.length})`}
          </button>
        )}
      </div>

      <div className="rolagem">
        <table>
          <thead>
            <tr>
              <th>String de busca</th>
              <th>Quando</th>
              <th className="num">Artigos</th>
              <th className="num">PDFs</th>
              <th className="num">Respostas</th>
              <th>Ações</th>
            </tr>
          </thead>
          <tbody>
            {visiveis.map((busca) => {
              const eAtiva = busca.id === ativa?.id;
              const removendo = removendoId === busca.id;
              return (
                <tr key={busca.id} className={eAtiva ? "linha-ativa" : undefined}>
                  <td>
                    <div className="query-busca" title={busca.query}>
                      {busca.query}
                    </div>
                    {eAtiva && <span className="etiqueta ok">Aberta</span>}
                  </td>
                  <td className="meta">{formatarData(busca.criado_em)}</td>
                  <td className="num">{busca.artigos_total}</td>
                  <td className="num">{busca.artigos_baixados}</td>
                  <td className="num">{busca.respostas_escritas}</td>
                  <td>
                    <div className="acoes-linha">
                      {!eAtiva && (
                        <button
                          className="botao-compacto"
                          onClick={() => onSelecionar(busca)}
                        >
                          Abrir
                        </button>
                      )}
                      <button
                        className="botao-compacto perigo"
                        onClick={() => onRemover(busca)}
                        disabled={removendo}
                        title="Apagar esta linha com seus artigos, PDFs e respostas"
                      >
                        {removendo ? (
                          <>
                            <span className="girando" />
                            Apagando
                          </>
                        ) : (
                          "Apagar"
                        )}
                      </button>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
