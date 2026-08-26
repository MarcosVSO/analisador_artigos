import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { api, ErroApi, urlPdf } from "../api";
import { ETIQUETAS, formatarAutores } from "../componentes/etiquetas";
import type { PainelRespostas } from "../tipos";

/** Quanto tempo sem digitar antes de gravar. Salvar a cada tecla geraria uma
 *  requisicao por caractere; esperar o "Salvar" perderia texto se a aba
 *  fechasse. */
const ESPERA_AUTOSALVAR_MS = 900;

type EstadoSalvamento = "ocioso" | "salvando" | "salvo" | "erro";

export function PaginaPerguntas() {
  const { artigoId } = useParams<{ artigoId: string }>();
  const id = Number(artigoId);

  const [painel, setPainel] = useState<PainelRespostas | null>(null);
  const [rascunhos, setRascunhos] = useState<Record<number, string>>({});
  const [estados, setEstados] = useState<Record<number, EstadoSalvamento>>({});
  const [erro, setErro] = useState<string | null>(null);
  const [carregando, setCarregando] = useState(true);

  const temporizadores = useRef<Record<number, ReturnType<typeof setTimeout>>>({});

  useEffect(() => {
    if (!Number.isFinite(id)) return;
    setCarregando(true);
    api
      .obterRespostas(id)
      .then((p) => {
        setPainel(p);
        setRascunhos(Object.fromEntries(p.itens.map((i) => [i.pergunta_id, i.texto])));
      })
      .catch((e) => setErro(e instanceof ErroApi ? e.message : "Falha ao carregar."))
      .finally(() => setCarregando(false));
  }, [id]);

  // Limpa temporizadores pendentes ao desmontar, senao um autosave dispara
  // depois que a tela ja saiu e escreve num artigo que nao esta mais aberto.
  useEffect(() => {
    const pendentes = temporizadores.current;
    return () => Object.values(pendentes).forEach(clearTimeout);
  }, []);

  const gravar = useCallback(
    async (perguntaId: number, texto: string) => {
      setEstados((s) => ({ ...s, [perguntaId]: "salvando" }));
      try {
        await api.salvarResposta(id, perguntaId, texto);
        setEstados((s) => ({ ...s, [perguntaId]: "salvo" }));
      } catch (e) {
        setEstados((s) => ({ ...s, [perguntaId]: "erro" }));
        if (e instanceof ErroApi) setErro(e.message);
      }
    },
    [id],
  );

  function aoDigitar(perguntaId: number, texto: string) {
    setRascunhos((r) => ({ ...r, [perguntaId]: texto }));
    setEstados((s) => ({ ...s, [perguntaId]: "ocioso" }));
    clearTimeout(temporizadores.current[perguntaId]);
    temporizadores.current[perguntaId] = setTimeout(
      () => void gravar(perguntaId, texto),
      ESPERA_AUTOSALVAR_MS,
    );
  }

  if (carregando) {
    return (
      <div className="pagina">
        <div className="cartao vazio">
          <span className="girando" /> Carregando…
        </div>
      </div>
    );
  }

  if (!painel) {
    return (
      <div className="pagina">
        <div className="aviso erro">{erro ?? "Artigo não encontrado."}</div>
        <Link to="/">← Voltar para a listagem</Link>
      </div>
    );
  }

  const { artigo } = painel;
  const etiqueta = ETIQUETAS[artigo.pdf_status] ?? ETIQUETAS.pendente;
  const respondidas = painel.itens.filter((i) =>
    (rascunhos[i.pergunta_id] ?? "").trim(),
  ).length;

  return (
    <div className="pagina">
      <div className="trilha">
        <Link to="/">← Listagem de artigos</Link>
      </div>

      <div className="cartao">
        <h1 className="titulo-pagina">{artigo.titulo}</h1>
        <div className="meta">
          {formatarAutores(artigo.autores)}
          {artigo.venue && ` · ${artigo.venue}`}
          {artigo.ano && ` · ${artigo.ano}`}
        </div>
        <div style={{ marginTop: 10, display: "flex", gap: 10, alignItems: "center" }}>
          <span className={`etiqueta ${etiqueta.classe}`}>{etiqueta.texto}</span>
          {artigo.baixado && (
            <a
              className="botao-pdf"
              href={urlPdf(artigo.id)}
              target="_blank"
              rel="noreferrer"
            >
              Abrir PDF
            </a>
          )}
          {artigo.doi && (
            <a
              className="meta"
              href={`https://doi.org/${artigo.doi}`}
              target="_blank"
              rel="noreferrer"
            >
              doi:{artigo.doi}
            </a>
          )}
        </div>
      </div>

      {erro && <div className="aviso erro">{erro}</div>}

      {painel.itens.length === 0 ? (
        <div className="cartao vazio">
          Nenhuma pergunta de pesquisa cadastrada. Volte para a listagem e use o
          botão <strong>Perguntas de pesquisa</strong> para criar as suas.
        </div>
      ) : (
        <>
          <div className="cartao" style={{ paddingBottom: 12 }}>
            <strong>
              {respondidas} de {painel.itens.length} respondidas
            </strong>
            <div className="meta">
              As respostas são salvas sozinhas, cerca de 1 s depois que você para
              de digitar.
            </div>
          </div>

          {painel.itens.map((item, indice) => {
            const estado = estados[item.pergunta_id] ?? "ocioso";
            return (
              <div className="cartao" key={item.pergunta_id}>
                <label htmlFor={`r-${item.pergunta_id}`} className="rotulo-pergunta">
                  {indice + 1}. {item.pergunta_texto}
                </label>
                <textarea
                  id={`r-${item.pergunta_id}`}
                  value={rascunhos[item.pergunta_id] ?? ""}
                  onChange={(e) => aoDigitar(item.pergunta_id, e.target.value)}
                  placeholder="Resposta, com a passagem do artigo que a sustenta…"
                  style={{ minHeight: 110, fontFamily: "inherit", fontSize: 14 }}
                />
                <div className="estado-salvamento meta">
                  {estado === "salvando" && (
                    <>
                      <span className="girando" />
                      salvando…
                    </>
                  )}
                  {estado === "salvo" && "✓ salvo"}
                  {estado === "erro" && "não consegui salvar"}
                </div>
              </div>
            );
          })}
        </>
      )}
    </div>
  );
}
