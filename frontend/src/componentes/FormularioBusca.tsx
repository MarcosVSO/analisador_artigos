import { useState } from "react";

interface Props {
  queryInicial: string;
  ocupado: boolean;
  onBuscar: (query: string) => void;
}

export function FormularioBusca({ queryInicial, ocupado, onBuscar }: Props) {
  const [query, setQuery] = useState(queryInicial);

  // `queryInicial` chega depois, quando /api/configuracao responde. Sem isso o
  // campo ficaria vazio para sempre, porque useState so le o valor uma vez.
  const [ultimaInicial, setUltimaInicial] = useState(queryInicial);
  if (queryInicial !== ultimaInicial) {
    setUltimaInicial(queryInicial);
    if (!query.trim()) setQuery(queryInicial);
  }

  function enviar(evento: React.FormEvent) {
    evento.preventDefault();
    if (query.trim().length >= 3 && !ocupado) onBuscar(query.trim());
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
              "Buscar no Scopus"
            )}
          </button>
        </div>
        <div>
          <span className="meta">
            Traz todos os resultados da query. O download dos PDFs é um passo
            separado.
          </span>
        </div>
      </div>
    </form>
  );
}
