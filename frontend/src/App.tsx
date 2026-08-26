import { useCallback, useEffect, useRef, useState } from "react";

import { api, ErroApi } from "./api";
import { FiltrosArtigos } from "./componentes/FiltrosArtigos";
import { FormularioBusca } from "./componentes/FormularioBusca";
import { ModalArtigo } from "./componentes/ModalArtigo";
import { PainelProgresso } from "./componentes/PainelProgresso";
import { TabelaArtigos } from "./componentes/TabelaArtigos";
import type {
  Artigo,
  Busca,
  Configuracao,
  Filtros,
  PaginaArtigos,
  Progresso,
} from "./tipos";

const INTERVALO_POLL_MS = 3000;
const FILTROS_VAZIOS: Filtros = { texto: "", baixado: null, paywall: null };

export default function App() {
  const [config, setConfig] = useState<Configuracao | null>(null);
  const [busca, setBusca] = useState<Busca | null>(null);
  const [progresso, setProgresso] = useState<Progresso | null>(null);
  const [pagina, setPagina] = useState<PaginaArtigos | null>(null);

  const [filtros, setFiltros] = useState<Filtros>(FILTROS_VAZIOS);
  const [numeroPagina, setNumeroPagina] = useState(1);
  const [detalhado, setDetalhado] = useState<Artigo | null>(null);

  const [buscando, setBuscando] = useState(false);
  const [carregando, setCarregando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

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
    async (buscaId: number, numero: number, comSpinner: boolean) => {
      if (comSpinner) setCarregando(true);
      try {
        const [novoProgresso, novaPagina] = await Promise.all([
          api.progresso(buscaId),
          api.listarArtigos(buscaId, filtros, numero),
        ]);
        setProgresso(novoProgresso);
        setPagina(novaPagina);
      } catch (e) {
        if (e instanceof ErroApi) setErro(e.message);
      } finally {
        if (comSpinner) setCarregando(false);
      }
    },
    [filtros],
  );

  // Um filtro novo pode deixar menos paginas do que a atual; voltar para a 1
  // evita cair numa pagina vazia.
  const primeiraRenderizacao = useRef(true);
  useEffect(() => {
    if (primeiraRenderizacao.current) {
      primeiraRenderizacao.current = false;
      return;
    }
    setNumeroPagina(1);
  }, [filtros]);

  useEffect(() => {
    if (busca) void recarregar(busca.id, numeroPagina, true);
  }, [busca, numeroPagina, recarregar]);

  // Enquanto o download roda, atualiza sozinho; para de consultar quando acaba.
  useEffect(() => {
    if (!busca || !progresso?.em_andamento) return;
    const timer = setInterval(
      () => void recarregar(busca.id, numeroPagina, false),
      INTERVALO_POLL_MS,
    );
    return () => clearInterval(timer);
  }, [busca, progresso?.em_andamento, numeroPagina, recarregar]);

  async function aoBuscar(query: string) {
    setBuscando(true);
    setErro(null);
    setProgresso(null);
    setPagina(null);
    setFiltros(FILTROS_VAZIOS);
    setNumeroPagina(1);
    try {
      const nova = await api.criarBusca(query);
      setBusca(nova);
    } catch (e) {
      setErro(e instanceof ErroApi ? e.message : "Falha inesperada na busca.");
    } finally {
      setBuscando(false);
    }
  }

  async function aoBaixar(incluirFalhas: boolean) {
    if (!busca) return;
    setErro(null);
    try {
      setProgresso(await api.baixarPdfs(busca.id, incluirFalhas));
    } catch (e) {
      if (e instanceof ErroApi) setErro(e.message);
    }
  }

  return (
    <div className="pagina">
      <header className="cabecalho">
        <h1>Analisador de Artigos</h1>
        <p>
          Busca no Scopus, download dos PDFs em acesso aberto e catalogação para a
          revisão bibliográfica.
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
        <>
          <PainelProgresso busca={busca} progresso={progresso} onBaixar={aoBaixar} />
          <FiltrosArtigos filtros={filtros} onMudar={setFiltros} />
        </>
      )}

      <TabelaArtigos
        pagina={pagina}
        carregando={carregando}
        onDetalhar={setDetalhado}
        onMudarPagina={setNumeroPagina}
      />

      {detalhado && (
        <ModalArtigo artigo={detalhado} onFechar={() => setDetalhado(null)} />
      )}
    </div>
  );
}
