import { useCallback, useEffect, useRef, useState } from "react";

import { api, ErroApi } from "../api";
import { DrawerPerguntas } from "../componentes/DrawerPerguntas";
import { FiltrosArtigos } from "../componentes/FiltrosArtigos";
import { FormularioBusca } from "../componentes/FormularioBusca";
import { ListaBuscas } from "../componentes/ListaBuscas";
import { ModalArtigo } from "../componentes/ModalArtigo";
import { PainelProgresso } from "../componentes/PainelProgresso";
import { TabelaArtigos } from "../componentes/TabelaArtigos";
import type {
  Artigo,
  Busca,
  Configuracao,
  Filtros,
  Ordenacao,
  PaginaArtigos,
  Progresso,
} from "../tipos";

const INTERVALO_POLL_MS = 3000;
const FILTROS_VAZIOS: Filtros = { texto: "", baixado: null, paywall: null };

export function PaginaListagem() {
  const [config, setConfig] = useState<Configuracao | null>(null);
  const [buscas, setBuscas] = useState<Busca[]>([]);
  const [busca, setBusca] = useState<Busca | null>(null);
  const [removendoId, setRemovendoId] = useState<number | null>(null);
  const [progresso, setProgresso] = useState<Progresso | null>(null);
  const [pagina, setPagina] = useState<PaginaArtigos | null>(null);

  const [filtros, setFiltros] = useState<Filtros>(FILTROS_VAZIOS);
  const [ordenarPor, setOrdenarPor] = useState<Ordenacao>("citacoes");
  const [numeroPagina, setNumeroPagina] = useState(1);

  const [detalhado, setDetalhado] = useState<Artigo | null>(null);
  const [drawerAberto, setDrawerAberto] = useState(false);
  const [totalPerguntas, setTotalPerguntas] = useState(0);
  const [baixandoIds, setBaixandoIds] = useState<Set<number>>(new Set());
  const [anexandoIds, setAnexandoIds] = useState<Set<number>>(new Set());

  const [buscando, setBuscando] = useState(false);
  const [carregando, setCarregando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  const carregarPerguntas = useCallback(() => {
    api
      .listarPerguntas()
      .then((p) => setTotalPerguntas(p.length))
      .catch(() => setTotalPerguntas(0));
  }, []);

  useEffect(() => {
    api.configuracao().then(setConfig).catch(() => setConfig(null));
    carregarPerguntas();
    api
      .listarBuscas()
      .then((lista) => {
        setBuscas(lista);
        if (lista.length) setBusca(lista[0]);
      })
      .catch(() => {
        /* backend fora do ar: o erro aparece quando o usuario buscar */
      });
  }, [carregarPerguntas]);

  const recarregarBuscas = useCallback(async () => {
    const lista = await api.listarBuscas();
    setBuscas(lista);
    return lista;
  }, []);

  const recarregar = useCallback(
    async (buscaId: number, numero: number, comSpinner: boolean) => {
      if (comSpinner) setCarregando(true);
      try {
        const [novoProgresso, novaPagina] = await Promise.all([
          api.progresso(buscaId),
          api.listarArtigos(buscaId, filtros, ordenarPor, numero),
        ]);
        setProgresso(novoProgresso);
        setPagina(novaPagina);
        // Um artigo que saiu de "pendente" terminou; libera o spinner da linha.
        setBaixandoIds((atuais) => {
          if (!atuais.size) return atuais;
          const restantes = new Set(atuais);
          for (const artigo of novaPagina.itens) {
            if (artigo.pdf_status !== "pendente") restantes.delete(artigo.id);
          }
          return restantes.size === atuais.size ? atuais : restantes;
        });
      } catch (e) {
        if (e instanceof ErroApi) setErro(e.message);
      } finally {
        if (comSpinner) setCarregando(false);
      }
    },
    [filtros, ordenarPor],
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
  }, [filtros, ordenarPor]);

  useEffect(() => {
    if (busca) void recarregar(busca.id, numeroPagina, true);
  }, [busca, numeroPagina, recarregar]);

  // Atualiza sozinho enquanto houver download rodando - em lote ou por linha.
  useEffect(() => {
    if (!busca) return;
    if (!progresso?.em_andamento && baixandoIds.size === 0) return;
    const timer = setInterval(
      () => void recarregar(busca.id, numeroPagina, false),
      INTERVALO_POLL_MS,
    );
    return () => clearInterval(timer);
  }, [busca, progresso?.em_andamento, baixandoIds.size, numeroPagina, recarregar]);

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
      await recarregarBuscas();
    } catch (e) {
      setErro(e instanceof ErroApi ? e.message : "Falha inesperada na busca.");
    } finally {
      setBuscando(false);
    }
  }

  function aoSelecionarBusca(escolhida: Busca) {
    setErro(null);
    setFiltros(FILTROS_VAZIOS);
    setNumeroPagina(1);
    setProgresso(null);
    setPagina(null);
    setBusca(escolhida);
  }

  async function aoRemoverBusca(alvo: Busca) {
    const partes = [
      `${alvo.artigos_total} artigos`,
      `${alvo.artigos_baixados} PDFs baixados`,
    ];
    if (alvo.respostas_escritas > 0) {
      partes.push(`${alvo.respostas_escritas} RESPOSTAS JÁ ESCRITAS`);
    }
    const confirmado = window.confirm(
      `Apagar esta linha de pesquisa?

${alvo.query}

` +
        `Serão apagados: ${partes.join(", ")}.

` +
        `Isto não pode ser desfeito. PDFs que você colocou na pasta à mão, ` +
        `sem vínculo com um artigo, não são tocados.`,
    );
    if (!confirmado) return;

    setErro(null);
    setRemovendoId(alvo.id);
    try {
      await api.removerBusca(alvo.id);
      const lista = await recarregarBuscas();
      if (busca?.id === alvo.id) {
        const proxima = lista[0] ?? null;
        setProgresso(null);
        setPagina(null);
        setFiltros(FILTROS_VAZIOS);
        setNumeroPagina(1);
        setBusca(proxima);
      }
    } catch (e) {
      if (e instanceof ErroApi) setErro(e.message);
    } finally {
      setRemovendoId(null);
    }
  }

  async function aoBaixar(incluirFalhas: boolean, limite?: number) {
    if (!busca) return;
    setErro(null);
    try {
      setProgresso(await api.baixarPdfs(busca.id, incluirFalhas, limite));
    } catch (e) {
      if (e instanceof ErroApi) setErro(e.message);
    }
  }

  async function aoAnexarPdf(artigo: Artigo, arquivo: File) {
    setErro(null);
    setAnexandoIds((atuais) => new Set(atuais).add(artigo.id));
    try {
      await api.anexarPdf(artigo.id, arquivo);
      // Recarrega a pagina inteira em vez de so trocar a linha: o painel de
      // progresso tambem muda (um pendente a menos, um baixado a mais).
      if (busca) await recarregar(busca.id, numeroPagina, false);
    } catch (e) {
      if (e instanceof ErroApi) setErro(e.message);
    } finally {
      setAnexandoIds((atuais) => {
        const restantes = new Set(atuais);
        restantes.delete(artigo.id);
        return restantes;
      });
    }
  }

  async function aoBaixarArtigo(artigo: Artigo) {
    setErro(null);
    setBaixandoIds((atuais) => new Set(atuais).add(artigo.id));
    try {
      await api.baixarArtigo(artigo.id);
    } catch (e) {
      setBaixandoIds((atuais) => {
        const restantes = new Set(atuais);
        restantes.delete(artigo.id);
        return restantes;
      });
      if (e instanceof ErroApi) setErro(e.message);
    }
  }

  return (
    <div className="pagina">
      <header className="cabecalho">
        <div className="cabecalho-topo">
          <div>
            <h1>Analisador de Artigos</h1>
            <p>
              Busca no Scopus, download dos PDFs em acesso aberto e catalogação
              para a revisão bibliográfica.
            </p>
          </div>
          <button onClick={() => setDrawerAberto(true)}>
            Perguntas de pesquisa{totalPerguntas ? ` (${totalPerguntas})` : ""}
          </button>
        </div>
      </header>

      {config && !config.credenciais_ok && (
        <div className="aviso atencao">{config.aviso}</div>
      )}

      {erro && <div className="aviso erro">{erro}</div>}

      <FormularioBusca
        queryInicial={config?.query_padrao ?? ""}
        ocupado={buscando}
        onBuscar={aoBuscar}
      />

      <ListaBuscas
        buscas={buscas}
        ativa={busca}
        removendoId={removendoId}
        onSelecionar={aoSelecionarBusca}
        onRemover={aoRemoverBusca}
      />

      {busca && (
        <>
          <PainelProgresso busca={busca} progresso={progresso} onBaixar={aoBaixar} />
          <FiltrosArtigos
            filtros={filtros}
            ordenarPor={ordenarPor}
            onMudar={setFiltros}
            onMudarOrdem={setOrdenarPor}
          />
        </>
      )}

      <TabelaArtigos
        pagina={pagina}
        carregando={carregando}
        baixandoIds={baixandoIds}
        anexandoIds={anexandoIds}
        onDetalhar={setDetalhado}
        onBaixarArtigo={aoBaixarArtigo}
        onAnexarPdf={aoAnexarPdf}
        onMudarPagina={setNumeroPagina}
      />

      {detalhado && (
        <ModalArtigo artigo={detalhado} onFechar={() => setDetalhado(null)} />
      )}

      <DrawerPerguntas
        aberto={drawerAberto}
        onFechar={() => setDrawerAberto(false)}
        onMudou={carregarPerguntas}
      />
    </div>
  );
}
