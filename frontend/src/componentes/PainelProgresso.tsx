import type { Busca, Progresso } from "../tipos";

interface Props {
  busca: Busca;
  progresso: Progresso | null;
  onBaixar: (incluirFalhas: boolean) => void;
}

export function PainelProgresso({ busca, progresso, onBaixar }: Props) {
  const total = progresso?.total ?? busca.novos;
  const baixados = progresso?.baixados ?? 0;
  const pendentes = progresso?.pendentes ?? total;
  const falhas = (progresso?.paywall ?? 0) + (progresso?.landing ?? 0) + (progresso?.erro ?? 0);
  const processados = total - pendentes;
  const fracao = total ? processados / total : 0;
  const rodando = progresso?.em_andamento ?? false;
  const aBaixar = progresso?.a_baixar ?? 0;

  // A Scopus achou mais do que o limite de seguranca conseguiu trazer.
  const truncada = busca.recuperados < busca.total_scopus;

  return (
    <div className="cartao">
      <div className="painel-topo">
        <div>
          <strong>
            {busca.total_scopus.toLocaleString("pt-BR")} resultados no Scopus
          </strong>
          <div className="meta">
            {busca.recuperados} recuperados · {busca.novos} salvos após deduplicação
          </div>
          {busca.arquivo_bruto && (
            <div className="meta">resposta bruta: {busca.arquivo_bruto}</div>
          )}
        </div>

        <div className="painel-acoes">
          <button
            className="primario"
            onClick={() => onBaixar(false)}
            disabled={rodando || aBaixar === 0}
            title="Baixa os artigos que ainda não foram tentados"
          >
            {rodando ? (
              <>
                <span className="girando" />
                Baixando…
              </>
            ) : (
              `Baixar pendentes${aBaixar ? ` (${aBaixar})` : ""}`
            )}
          </button>
          {!rodando && falhas > 0 && (
            <button
              onClick={() => onBaixar(true)}
              title="Refaz a resolução dos que ficaram como paywall ou falha"
            >
              Tentar novamente ({falhas})
            </button>
          )}
        </div>
      </div>

      {truncada && (
        <div className="aviso atencao" style={{ marginTop: 12, marginBottom: 0 }}>
          A query tem {busca.total_scopus.toLocaleString("pt-BR")} resultados e o
          limite de segurança trouxe {busca.recuperados}. Refine a busca ou aumente
          <code> LIMITE_SEGURANCA</code> no <code>.env</code>.
        </div>
      )}

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
        <Contador valor={pendentes} rotulo="pendente" />
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
