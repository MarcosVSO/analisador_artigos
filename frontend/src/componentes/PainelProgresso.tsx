import type { Busca, Progresso } from "../tipos";

interface Props {
  busca: Busca;
  progresso: Progresso | null;
  onBaixar: () => void;
}

export function PainelProgresso({ busca, progresso, onBaixar }: Props) {
  const total = progresso?.total ?? busca.novos;
  const baixados = progresso?.baixados ?? 0;
  const resolvidos = total - (progresso?.pendentes ?? total);
  const fracao = total ? resolvidos / total : 0;
  const rodando = progresso?.em_andamento ?? false;

  return (
    <div className="cartao">
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          gap: 16,
          flexWrap: "wrap",
        }}
      >
        <div>
          <strong>
            {busca.total_scopus.toLocaleString("pt-BR")} resultados no Scopus
          </strong>
          <div className="meta">
            {busca.recuperados} recuperados · {busca.novos} salvos após deduplicação
            {busca.arquivo_bruto && ` · resposta bruta em ${busca.arquivo_bruto}`}
          </div>
        </div>
        <button onClick={onBaixar} disabled={rodando}>
          {rodando ? (
            <>
              <span className="girando" />
              Baixando…
            </>
          ) : (
            "Baixar PDFs pendentes"
          )}
        </button>
      </div>

      <div className="barra">
        <div style={{ width: `${Math.round(fracao * 100)}%` }} />
      </div>

      <div className="contadores">
        <Contador valor={total} rotulo="artigos" />
        <Contador valor={baixados} rotulo="PDF baixado" />
        <Contador
          valor={(progresso?.paywall ?? 0) + (progresso?.landing ?? 0)}
          rotulo="paywall"
        />
        <Contador valor={progresso?.erro ?? 0} rotulo="falha" />
        <Contador valor={progresso?.pendentes ?? 0} rotulo="pendente" />
        {total > 0 && (
          <Contador
            valor={`${Math.round((baixados / total) * 100)}%`}
            rotulo="taxa de download"
          />
        )}
      </div>
    </div>
  );
}

function Contador({ valor, rotulo }: { valor: number | string; rotulo: string }) {
  return (
    <div className="contador">
      <div className="valor">{valor}</div>
      <div className="rotulo">{rotulo}</div>
    </div>
  );
}
