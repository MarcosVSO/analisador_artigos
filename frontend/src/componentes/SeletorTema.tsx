import { useEffect, useState } from "react";

export type Tema = "sistema" | "claro" | "escuro";

const CHAVE = "analisador:tema";

/** Le a escolha guardada. Fora do componente porque o index.html aplica o
 *  mesmo valor antes do React montar, para nao piscar o tema errado. */
export function temaGuardado(): Tema {
  try {
    const valor = localStorage.getItem(CHAVE);
    if (valor === "claro" || valor === "escuro") return valor;
  } catch {
    /* modo privativo pode bloquear o localStorage */
  }
  return "sistema";
}

export function aplicarTema(tema: Tema): void {
  const raiz = document.documentElement;
  if (tema === "sistema") raiz.removeAttribute("data-tema");
  else raiz.setAttribute("data-tema", tema);
  try {
    if (tema === "sistema") localStorage.removeItem(CHAVE);
    else localStorage.setItem(CHAVE, tema);
  } catch {
    /* sem persistencia: a escolha vale so nesta aba */
  }
}

const OPCOES: { valor: Tema; rotulo: string; icone: string }[] = [
  { valor: "claro", rotulo: "Tema claro", icone: "☀" },
  { valor: "escuro", rotulo: "Tema escuro", icone: "☾" },
  { valor: "sistema", rotulo: "Seguir o sistema", icone: "◐" },
];

export function SeletorTema() {
  const [tema, setTema] = useState<Tema>(temaGuardado);

  useEffect(() => {
    aplicarTema(tema);
  }, [tema]);

  return (
    <div className="seletor-tema" role="group" aria-label="Tema da interface">
      {OPCOES.map((o) => (
        <button
          key={o.valor}
          className={o.valor === tema ? "ativo" : undefined}
          onClick={() => setTema(o.valor)}
          title={o.rotulo}
          aria-label={o.rotulo}
          aria-pressed={o.valor === tema}
        >
          {o.icone}
        </button>
      ))}
    </div>
  );
}
