import { useCallback, useEffect, useState } from "react";

import { api, ErroApi } from "./api";
import { FormularioBusca } from "./componentes/FormularioBusca";
import { PainelProgresso } from "./componentes/PainelProgresso";
import { TabelaArtigos } from "./componentes/TabelaArtigos";
import type { Artigo, Busca, Configuracao, Progresso, Situacao } from "./tipos";

const INTERVALO_POLL_MS = 3000;

export default function App() {
  const [config, setConfig] = useState<Configuracao | null>(null);
  const [busca, setBusca] = useState<Busca | null>(null);
  const [progresso, setProgresso] = useState<Progresso | null>(null);
  const [artigos, setArtigos] = useState<Artigo[]>([]);

  const [situacao, setSituacao] = useState<Situacao>("todos");
  const [texto, setTexto] = useState("");

  const [buscando, setBuscando] = useState(false);
  const [carregandoArtigos, setCarregandoArtigos] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  // Config e a busca mais recente, para a pagina abrir ja com contexto.
  useEffect(() => {
    api.configuracao().then(setConfig).catch(() => setConfig(null));
    api
      .listarBuscas()
      .then((lista) => {
        if (lista.length) setBusca(lista[0]);
      })
      .catch(() => {
        /* backend fora do ar: o erro aparece quando o usuario buscar */
      });
  }, []);

  const recarregar = useCallback(
    async (buscaId: number, comSpinner: boolean) => {
      if (comSpinner) setCarregandoArtigos(true);
      try {
        const [novoProgresso, novosArtigos] = await Promise.all([
          api.progresso(buscaId),
          api.listarArtigos(buscaId, situacao, texto),
        ]);
        setProgresso(novoProgresso);
        setArtigos(novosArtigos);
      } catch (e) {
        if (e instanceof ErroApi) setErro(e.message);
      } finally {
        if (comSpinner) setCarregandoArtigos(false);
      }
    },
    [situacao, texto],
  );

  // Recarrega ao trocar de busca ou de filtro.
  useEffect(() => {
    if (busca) void recarregar(busca.id, true);
  }, [busca, recarregar]);

  // Enquanto o download roda, atualiza sozinho. O intervalo e desmontado
  // assim que `em_andamento` vira false, entao a pagina para de bater no
  // backend quando nao ha mais nada acontecendo.
  useEffect(() => {
    if (!busca || !progresso?.em_andamento) return;
    const timer = setInterval(() => void recarregar(busca.id, false), INTERVALO_POLL_MS);
    return () => clearInterval(timer);
  }, [busca, progresso?.em_andamento, recarregar]);

  async function aoBuscar(query: string, maxResultados: number) {
    setBuscando(true);
    setErro(null);
    setProgresso(null);
    setArtigos([]);
    try {
      const nova = await api.criarBusca(query, maxResultados);
      setBusca(nova);
      // O backend ja disparou o download; um poll imediato acende a barra.
      await recarregar(nova.id, true);
    } catch (e) {
      setErro(e instanceof ErroApi ? e.message : "Falha inesperada na busca.");
    } finally {
      setBuscando(false);
    }
  }

  async function aoBaixar() {
    if (!busca) return;
    setErro(null);
    try {
      setProgresso(await api.baixarPdfs(busca.id));
    } catch (e) {
      if (e instanceof ErroApi) setErro(e.message);
    }
  }

  return (
    <div className="pagina">
      <header className="cabecalho">
        <h1>Analisador de Artigos</h1>
        <p>
          Busca no Scopus, download automático dos PDFs em acesso aberto e
          catalogação para a revisão bibliográfica.
        </p>
      </header>

      {config && !config.credenciais_ok && (
        <div className="aviso atencao">{config.aviso}</div>
      )}

      {config?.view_scopus === "STANDARD" && (
        <div className="aviso atencao">
          A chave do Scopus não tem acesso a <code>view=COMPLETE</code>, então a
          busca não traz abstract. Os abstracts são preenchidos pelo OpenAlex, por
          DOI, sem consumir quota.
        </div>
      )}

      {erro && <div className="aviso erro">{erro}</div>}

      <FormularioBusca
        queryInicial={config?.query_padrao ?? ""}
        ocupado={buscando}
        onBuscar={aoBuscar}
      />

      {busca && (
        <PainelProgresso busca={busca} progresso={progresso} onBaixar={aoBaixar} />
      )}

      {busca && (
        <div className="cartao">
          <div className="linha-controles" style={{ marginTop: 0 }}>
            <div className="crescer">
              <label htmlFor="filtro-texto">Filtrar por título</label>
              <input
                id="filtro-texto"
                value={texto}
                onChange={(e) => setTexto(e.target.value)}
                placeholder="ex.: volumetric"
              />
            </div>
            <div>
              <label htmlFor="filtro-situacao">Situação do PDF</label>
              <select
                id="filtro-situacao"
                value={situacao}
                onChange={(e) => setSituacao(e.target.value as Situacao)}
              >
                <option value="todos">Todos</option>
                <option value="baixados">Só com PDF baixado</option>
                <option value="sem_pdf">Só sem PDF</option>
              </select>
            </div>
          </div>
        </div>
      )}

      <TabelaArtigos artigos={artigos} carregando={carregandoArtigos} />
    </div>
  );
}
