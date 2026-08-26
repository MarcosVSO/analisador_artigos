import { useEffect, useState } from "react";

import { api, ErroApi } from "../api";
import type { Pergunta } from "../tipos";

interface Props {
  aberto: boolean;
  onFechar: () => void;
  onMudou: () => void;
}

export function DrawerPerguntas({ aberto, onFechar, onMudou }: Props) {
  const [perguntas, setPerguntas] = useState<Pergunta[]>([]);
  const [nova, setNova] = useState("");
  const [editando, setEditando] = useState<number | null>(null);
  const [textoEdicao, setTextoEdicao] = useState("");
  const [erro, setErro] = useState<string | null>(null);
  const [salvando, setSalvando] = useState(false);

  useEffect(() => {
    if (!aberto) return;
    api.listarPerguntas().then(setPerguntas).catch(() => setPerguntas([]));
  }, [aberto]);

  useEffect(() => {
    if (!aberto) return;
    function aoTeclar(evento: KeyboardEvent) {
      if (evento.key === "Escape") onFechar();
    }
    document.addEventListener("keydown", aoTeclar);
    return () => document.removeEventListener("keydown", aoTeclar);
  }, [aberto, onFechar]);

  async function recarregar() {
    setPerguntas(await api.listarPerguntas());
    onMudou();
  }

  async function adicionar(evento: React.FormEvent) {
    evento.preventDefault();
    if (nova.trim().length < 3) return;
    setSalvando(true);
    setErro(null);
    try {
      await api.criarPergunta(nova.trim());
      setNova("");
      await recarregar();
    } catch (e) {
      if (e instanceof ErroApi) setErro(e.message);
    } finally {
      setSalvando(false);
    }
  }

  async function salvarEdicao(id: number) {
    if (textoEdicao.trim().length < 3) return;
    try {
      await api.atualizarPergunta(id, { texto: textoEdicao.trim() });
      setEditando(null);
      await recarregar();
    } catch (e) {
      if (e instanceof ErroApi) setErro(e.message);
    }
  }

  async function remover(pergunta: Pergunta) {
    // Apagar leva junto as respostas ja escritas para essa pergunta em todos
    // os artigos - por isso a confirmacao diz isso em vez de "tem certeza?".
    const confirmado = window.confirm(
      `Apagar "${pergunta.texto}"?\n\nAs respostas já escritas para esta ` +
        `pergunta, em todos os artigos, serão apagadas junto.`,
    );
    if (!confirmado) return;
    try {
      await api.removerPergunta(pergunta.id);
      await recarregar();
    } catch (e) {
      if (e instanceof ErroApi) setErro(e.message);
    }
  }

  if (!aberto) return null;

  return (
    <div className="fundo-modal" onClick={onFechar} role="presentation">
      <aside
        className="drawer"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label="Perguntas de pesquisa"
      >
        <div className="modal-cabecalho">
          <h2>Perguntas de pesquisa</h2>
          <button className="fechar" onClick={onFechar} aria-label="Fechar">
            ×
          </button>
        </div>

        <div className="modal-corpo">
          <p className="meta" style={{ marginTop: 0 }}>
            Valem para todos os artigos, inclusive os de buscas futuras. Cada
            artigo tem sua própria tela de respostas.
          </p>

          {erro && <div className="aviso erro">{erro}</div>}

          <form onSubmit={adicionar} style={{ marginBottom: 20 }}>
            <label htmlFor="nova-pergunta">Nova pergunta</label>
            <textarea
              id="nova-pergunta"
              value={nova}
              onChange={(e) => setNova(e.target.value)}
              placeholder="ex.: O trabalho usa HMD nos experimentos? Qual modelo?"
              style={{ minHeight: 72 }}
            />
            <button
              type="submit"
              className="primario"
              disabled={salvando || nova.trim().length < 3}
              style={{ marginTop: 8 }}
            >
              Adicionar
            </button>
          </form>

          {perguntas.length === 0 ? (
            <p className="meta">Nenhuma pergunta ainda.</p>
          ) : (
            <ol className="lista-perguntas">
              {perguntas.map((p) => (
                <li key={p.id}>
                  {editando === p.id ? (
                    <>
                      <textarea
                        value={textoEdicao}
                        onChange={(e) => setTextoEdicao(e.target.value)}
                        style={{ minHeight: 64 }}
                      />
                      <div className="acoes-pergunta">
                        <button className="primario" onClick={() => salvarEdicao(p.id)}>
                          Salvar
                        </button>
                        <button onClick={() => setEditando(null)}>Cancelar</button>
                      </div>
                    </>
                  ) : (
                    <>
                      <div>{p.texto}</div>
                      <div className="acoes-pergunta">
                        <button
                          onClick={() => {
                            setEditando(p.id);
                            setTextoEdicao(p.texto);
                          }}
                        >
                          Editar
                        </button>
                        <button onClick={() => remover(p)}>Apagar</button>
                      </div>
                    </>
                  )}
                </li>
              ))}
            </ol>
          )}
        </div>
      </aside>
    </div>
  );
}
