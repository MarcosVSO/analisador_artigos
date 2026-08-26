import { useState } from "react";

interface Props {
  queryInicial: string;
  ocupado: boolean;
  onBuscar: (query: string, maxResultados: number) => void;
}

export function FormularioBusca({ queryInicial, ocupado, onBuscar }: Props) {
  const [query, setQuery] = useState(queryInicial);
  const [maxResultados, setMaxResultados] = useState(200);

  // `queryInicial` chega depois, quando /api/configuracao responde. Sem isso o
  // campo ficaria vazio para sempre, porque useState so le o valor uma vez.
  const [ultimaInicial, setUltimaInicial] = useState(queryInicial);
  if (queryInicial !== ultimaInicial) {
    setUltimaInicial(queryInicial);
    if (!query.trim()) setQuery(queryInicial);
  }

  function enviar(evento: React.FormEvent) {
    evento.preventDefault();
    if (query.trim().length >= 3 && !ocupado) {
      onBuscar(query.trim(), maxResultados);
    }
  }

  return (
    <form className="cartao" onSubmit={enviar}>
      <label htmlFor="query">String de busca (sintaxe do Scopus)</label>
      <textarea
        id="query"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder='TITLE-ABS-KEY("volumetric video" AND streaming) AND PUBYEAR > 2023'
        spellCheck={false}
      />

      <div className="linha-controles">
        <div>
          <label htmlFor="max">Máx. resultados</label>
          <input
            id="max"
            type="number"
            min={1}
            max={5000}
            step={25}
            value={maxResultados}
            onChange={(e) => setMaxResultados(Number(e.target.value) || 1)}
            style={{ width: 120 }}
          />
        </div>
        <div>
          <button
            type="submit"
            className="primario"
            disabled={ocupado || query.trim().length < 3}
          >
            {ocupado ? (
              <>
                <span className="girando" />
                Buscando…
              </>
            ) : (
              "Buscar no Scopus e baixar PDFs"
            )}
          </button>
        </div>
      </div>
    </form>
  );
}
