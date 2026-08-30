import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface Props {
  children: string;
}

/** Renderiza a resposta da IA, que vem em Markdown.
 *
 *  `react-markdown` monta elementos React em vez de injetar HTML, e NAO
 *  interpreta HTML cru sem o plugin `rehype-raw`. Isso importa aqui: o texto
 *  e produzido por um modelo lendo PDFs de terceiros, entao tratar a saida
 *  como marcacao confiavel seria assumir que nenhum artigo consegue plantar
 *  conteudo na resposta.
 *
 *  `remark-gfm` acrescenta tabelas e listas de tarefa, que o modelo usa ao
 *  comparar artigos.
 */
export function Markdown({ children }: Props) {
  return (
    <div className="markdown">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          // Todo link externo abre em outra aba: a resposta e material de
          // trabalho, e perder a pagina no meio da leitura irrita.
          a: ({ href, children: filhos }) => (
            <a href={href} target="_blank" rel="noreferrer noopener">
              {filhos}
            </a>
          ),
          // Tabela precisa do proprio contenedor rolavel, senao uma
          // comparacao larga estoura a largura da pagina.
          table: ({ children: filhos }) => (
            <div className="rolagem">
              <table>{filhos}</table>
            </div>
          ),
        }}
      >
        {children}
      </ReactMarkdown>
    </div>
  );
}
