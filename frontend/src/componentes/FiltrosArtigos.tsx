import type { Filtros, Ordenacao } from "../tipos";

interface Props {
  filtros: Filtros;
  ordenarPor: Ordenacao;
  onMudar: (filtros: Filtros) => void;
  onMudarOrdem: (ordem: Ordenacao) => void;
}

/** "" no <select> representa o filtro desligado; o backend trata ausencia
 *  como "mostra os dois casos". */
function paraBooleano(valor: string): boolean | null {
  if (valor === "") return null;
  return valor === "sim";
}

function paraTexto(valor: boolean | null): string {
  if (valor === null) return "";
  return valor ? "sim" : "nao";
}

export function FiltrosArtigos({
  filtros,
  ordenarPor,
  onMudar,
  onMudarOrdem,
}: Props) {
  return (
    <div className="cartao">
      <div className="linha-controles" style={{ marginTop: 0 }}>
        <div className="crescer">
          <label htmlFor="filtro-texto">Filtrar por título</label>
          <input
            id="filtro-texto"
            value={filtros.texto}
            onChange={(e) => onMudar({ ...filtros, texto: e.target.value })}
            placeholder="ex.: volumetric"
          />
        </div>

        <div>
          <label htmlFor="filtro-baixado">Download</label>
          <select
            id="filtro-baixado"
            value={paraTexto(filtros.baixado)}
            onChange={(e) =>
              onMudar({ ...filtros, baixado: paraBooleano(e.target.value) })
            }
          >
            <option value="">Todos</option>
            <option value="sim">Baixados</option>
            <option value="nao">Não baixados</option>
          </select>
        </div>

        <div>
          <label htmlFor="filtro-paywall">Paywall</label>
          <select
            id="filtro-paywall"
            value={paraTexto(filtros.paywall)}
            onChange={(e) =>
              onMudar({ ...filtros, paywall: paraBooleano(e.target.value) })
            }
          >
            <option value="">Todos</option>
            <option value="sim">Com paywall</option>
            <option value="nao">Sem paywall</option>
          </select>
        </div>

        <div>
          <label htmlFor="ordenar">Ordenar por</label>
          <select
            id="ordenar"
            value={ordenarPor}
            onChange={(e) => onMudarOrdem(e.target.value as Ordenacao)}
          >
            <option value="citacoes">Citações (maior primeiro)</option>
            <option value="ano_desc">Ano (mais recente)</option>
            <option value="ano_asc">Ano (mais antigo)</option>
            <option value="titulo">Título (A–Z)</option>
          </select>
        </div>

        <div>
          <button
            onClick={() => onMudar({ texto: "", baixado: null, paywall: null })}
            disabled={
              !filtros.texto && filtros.baixado === null && filtros.paywall === null
            }
          >
            Limpar
          </button>
        </div>
      </div>
    </div>
  );
}
