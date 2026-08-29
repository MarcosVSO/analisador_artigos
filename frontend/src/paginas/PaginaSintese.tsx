import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { api, ErroApi, urlCsvMatriz } from "../api";
import type { Busca, ConsultaSintese, MatrizSintese } from "../tipos";

/** Perguntas prontas para o objetivo declarado: escrever um projeto de
 *  pesquisa. Servem de ponto de partida — o campo aceita qualquer texto. */
const SUGESTOES = [
  {
    rotulo: "Lacunas e contribuições",
    texto:
      "Com base nas respostas dos artigos analisados, quais lacunas você " +
      "identifica na literatura coberta por esta matriz? Para cada lacuna, " +
      "aponte quais células ou padrões ausentes a revelam e sugira uma " +
      "contribuição concreta que eu poderia fazer num projeto de mestrado.",
  },
  {
    rotulo: "Panorama das estratégias",
    texto:
      "Quais estratégias os artigos usam para resolver seus problemas? " +
      "Agrupe por família de abordagem, diga quantos artigos usam cada uma e " +
      "aponte qual está mais saturada e qual está menos explorada.",
  },
  {
    rotulo: "Rigor experimental",
    texto:
      "Como os artigos avaliam seus trabalhos? Compare o uso de HMD real, a " +
      "consideração da rede na avaliação e a disponibilização de dataset e " +
      "código. Onde está o ponto mais fraco do conjunto?",
  },
  {
    rotulo: "Contradições entre estudos",
    texto:
      "Há resultados ou escolhas de projeto que se contradizem entre os " +
      "artigos? Aponte quais e o que a divergência sugere sobre uma questão " +
      "ainda em aberto.",
  },
];

export function PaginaSintese() {
  const [buscas, setBuscas] = useState<Busca[]>([]);
  const [buscaId, setBuscaId] = useState<number | null>(null);
  const [somenteAnalisados, setSomenteAnalisados] = useState(true);

  const [matriz, setMatriz] = useState<MatrizSintese | null>(null);
  const [consultas, setConsultas] = useState<ConsultaSintese[]>([]);
  const [pergunta, setPergunta] = useState("");

  const [carregando, setCarregando] = useState(true);
  const [perguntando, setPerguntando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    api.listarBuscas().then(setBuscas).catch(() => setBuscas([]));
  }, []);

  const recarregar = useCallback(async () => {
    setCarregando(true);
    try {
      const [m, c] = await Promise.all([
        api.matriz(buscaId, somenteAnalisados),
        api.listarConsultas(buscaId),
      ]);
      setMatriz(m);
      setConsultas(c);
    } catch (e) {
      if (e instanceof ErroApi) setErro(e.message);
    } finally {
      setCarregando(false);
    }
  }, [buscaId, somenteAnalisados]);

  useEffect(() => {
    void recarregar();
  }, [recarregar]);

  async function perguntar() {
    if (pergunta.trim().length < 5) return;
    setPerguntando(true);
    setErro(null);
    try {
      const nova = await api.perguntarSintese(
        pergunta.trim(),
        buscaId,
        somenteAnalisados,
      );
      setConsultas((atuais) => [nova, ...atuais]);
      setPergunta("");
    } catch (e) {
      setErro(e instanceof ErroApi ? e.message : "Falha ao consultar.");
    } finally {
      setPerguntando(false);
    }
  }

  async function remover(id: number) {
    if (!window.confirm("Apagar esta consulta do histórico?")) return;
    try {
      await api.removerConsulta(id);
      setConsultas((atuais) => atuais.filter((c) => c.id !== id));
    } catch (e) {
      if (e instanceof ErroApi) setErro(e.message);
    }
  }

  const vazia = !matriz || matriz.total === 0;

  return (
    <div className="pagina pagina-larga">
      <div className="trilha">
        <Link to="/">← Listagem de artigos</Link>
      </div>

      <header className="cabecalho">
        <h1>Síntese da revisão</h1>
        <p>
          Os artigos analisados e suas respostas, lado a lado. As perguntas
          abaixo são respondidas <strong>com base nesta matriz</strong> — não na
          literatura da área.
        </p>
      </header>

      <div className="cartao">
        <div className="linha-controles" style={{ marginTop: 0 }}>
          <div className="crescer">
            <label htmlFor="linha">Linha de pesquisa</label>
            <select
              id="linha"
              value={buscaId ?? ""}
              onChange={(e) =>
                setBuscaId(e.target.value ? Number(e.target.value) : null)
              }
            >
              <option value="">Todas as linhas</option>
              {buscas.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.query.slice(0, 70)} ({b.artigos_total} artigos)
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="escopo">Escopo</label>
            <select
              id="escopo"
              value={somenteAnalisados ? "sim" : "nao"}
              onChange={(e) => setSomenteAnalisados(e.target.value === "sim")}
            >
              <option value="sim">Só analisados</option>
              <option value="nao">Todos os artigos</option>
            </select>
          </div>
          <div>
            <a
              className="botao-compacto"
              href={urlCsvMatriz(buscaId, somenteAnalisados)}
              title="Baixar a matriz em CSV para a planilha"
            >
              Exportar CSV
            </a>
          </div>
        </div>
        <div className="meta" style={{ marginTop: 10 }}>
          {carregando
            ? "Carregando…"
            : `${matriz?.total ?? 0} artigos × ${matriz?.perguntas.length ?? 0} perguntas`}
        </div>
      </div>

      {erro && <div className="aviso erro">{erro}</div>}

      {vazia && !carregando ? (
        <div className="cartao vazio">
          Nenhum artigo analisado ainda. Responda as perguntas de pesquisa de
          pelo menos um artigo — ou use o botão <strong>Analisar com IA</strong>{" "}
          na tela de perguntas.
        </div>
      ) : (
        matriz && (
          <div className="cartao">
            <div className="rolagem">
              <table className="matriz">
                <thead>
                  <tr>
                    <th className="coluna-fixa">Artigo</th>
                    {matriz.perguntas.map((p) => (
                      <th key={p.id} title={p.texto}>
                        {p.texto}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {matriz.artigos.map((a) => (
                    <tr key={a.artigo_id}>
                      <td className="coluna-fixa">
                        <Link
                          to={`/artigos/${a.artigo_id}/perguntas`}
                          className="titulo-artigo"
                        >
                          {a.titulo}
                        </Link>
                        <div className="meta">
                          {a.autores[0] ?? "—"}
                          {a.ano && ` · ${a.ano}`}
                        </div>
                      </td>
                      {matriz.perguntas.map((p) => (
                        <td key={p.id}>
                          <div className="celula-matriz">
                            {a.respostas[p.id]?.trim() || (
                              <span className="meta">—</span>
                            )}
                          </div>
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="rodape-tabela">
              Clique no título para abrir a tela de respostas do artigo. Células
              longas rolam sozinhas.
            </div>
          </div>
        )
      )}

      <div className="cartao">
        <label htmlFor="consulta">Pergunte sobre o conjunto</label>
        <textarea
          id="consulta"
          value={pergunta}
          onChange={(e) => setPergunta(e.target.value)}
          placeholder="ex.: Baseando-se nas respostas, quais lacunas eu poderia atacar num projeto de mestrado?"
          style={{ minHeight: 90, fontFamily: "inherit", fontSize: 14 }}
        />

        <div className="chips" style={{ marginTop: 10 }}>
          {SUGESTOES.map((s) => (
            <button
              key={s.rotulo}
              className="botao-compacto"
              onClick={() => setPergunta(s.texto)}
              disabled={perguntando}
            >
              {s.rotulo}
            </button>
          ))}
        </div>

        <div className="linha-controles">
          <div>
            <button
              className="primario"
              onClick={perguntar}
              disabled={perguntando || pergunta.trim().length < 5 || vazia}
            >
              {perguntando ? (
                <>
                  <span className="girando" />
                  Analisando a matriz…
                </>
              ) : (
                "Perguntar"
              )}
            </button>
          </div>
          <div>
            <span className="meta">
              {perguntando
                ? "Pode levar um minuto."
                : `Considera os ${matriz?.total ?? 0} artigos da matriz acima.`}
            </span>
          </div>
        </div>
      </div>

      {consultas.map((c) => (
        <div className="cartao consulta" key={c.id}>
          <div className="painel-topo">
            <strong className="pergunta-feita">{c.pergunta}</strong>
            <button className="botao-compacto perigo" onClick={() => remover(c.id)}>
              Apagar
            </button>
          </div>
          <div className="resposta-sintese">{c.resposta}</div>
          <div className="meta" style={{ marginTop: 10 }}>
            {new Date(
              c.criado_em.endsWith("Z") ? c.criado_em : `${c.criado_em}Z`,
            ).toLocaleString("pt-BR")}{" "}
            · {c.artigos_considerados} artigos
            {c.modelo && ` · ${c.modelo}`}
            {c.custo_usd ? ` · US$ ${c.custo_usd.toFixed(3)}` : ""}
          </div>
        </div>
      ))}
    </div>
  );
}
