# Analisador de Artigos

Sistema de apoio a revisão bibliográfica: busca no Scopus, download automático
dos PDFs em acesso aberto e catalogação dos artigos encontrados.

As etapas seguintes (análise por IA respondendo perguntas de pesquisa, dashboard
e detecção de lacunas) entram sobre esta base.

---

## Estrutura

```
backend/                  API FastAPI + SQLite
  app/
    config.py             caminhos e variáveis de ambiente
    banco.py              engine e sessão do SQLite
    modelos.py            tabelas: buscas, artigos, perguntas, respostas
                          (buscas = linhas de pesquisa; apagar faz cascade)
    esquemas.py           contratos de entrada/saída da API
    main.py               aplicação FastAPI
    rotas/
      buscas.py           linhas de pesquisa: criar, listar, apagar, progresso
      artigos.py          listagem filtrada, download por artigo, PDF
      perguntas.py        perguntas de pesquisa e respostas por artigo
    servicos/
      scopus.py           cliente da Scopus Search API
      openalex.py         enriquecimento de abstract e keywords
      resolvedor_pdf.py   cadeia de resolução de full-text
      analise_ia.py       análise do PDF pelo Claude
      analise_claude_code.py  executor headless da CLI
      estado_analise.py   recálculo da flag `analisado`
      sintese.py          matriz, CSV e consultas sobre o conjunto
      busca.py            orquestra Scopus → arquivo bruto → OpenAlex → banco
      download.py         download em background com pool de threads
  ferramentas/
    diagnostico_viabilidade.py   diagnóstico da API (ver ferramentas/README.md)

scripts/                  lançador e atalho
  iniciar.py              sobe backend + frontend, abre o navegador
  Analisador de Artigos.bat   alvo do atalho da Área de Trabalho
  criar_atalho.ps1        cria/remove o atalho
  gerar_icone.py          regenera scripts/icone.ico

frontend/                 React + Vite + TypeScript
  src/
    App.tsx               rotas
    api.ts                cliente HTTP
    tipos.ts              tipos compartilhados
    paginas/
      PaginaListagem.tsx  busca, filtros e tabela de artigos
      PaginaPerguntas.tsx respostas de um artigo
      PaginaSintese.tsx   matriz e consultas sobre o conjunto
    componentes/          formulário, lista de buscas, progresso, tabela,
                          modal, drawer, seletor de tema, markdown

dados/                    gerado em execução, fora do git
  pdfs/                   PDFs baixados
  respostas_scopus/       resposta bruta de cada busca, em JSON
  analisador.db           banco SQLite
```

---

## Configuração

```bash
cp .env.example .env
```

Preencha no `.env`:

| Variável | Onde conseguir | Obrigatória |
|---|---|---|
| `SCOPUS_API_KEY` | [dev.elsevier.com/apikey/manage](https://dev.elsevier.com/apikey/manage), login institucional | sim |
| `CONTACT_EMAIL` | um e-mail seu real; o Unpaywall exige | sim, na prática |
| `SCOPUS_QUERY` | sua string de busca padrão (pré-preenche o campo no frontend) | não |
| `SCOPUS_INSTTOKEN` | suporte da Elsevier — só fora da rede da universidade | não |

O `.env` está no `.gitignore`. Não coloque credencial em nenhum outro arquivo.

---

## Como rodar

### Pelo atalho na Área de Trabalho (recomendado)

Uma vez só, para criar o atalho:

```bash
powershell -ExecutionPolicy Bypass -File scripts\criar_atalho.ps1
```

Depois é só clicar em **Analisador de Artigos** na Área de Trabalho. O
lançador sobe backend e frontend, espera os dois responderem e abre o
navegador. Fechar a janela desliga tudo.

Clicar de novo com o sistema já no ar apenas reabre a aba, sem tentar subir
nada. Para remover o atalho: `... criar_atalho.ps1 -Remover`.

Logs de cada servidor ficam em `dados/logs/`.

### Pelo terminal

```bash
python scripts/iniciar.py
```

Ou os dois servidores separados, para desenvolvimento:

```bash
python -m uvicorn app.main:app --reload --port 8000 --app-dir backend
```

```bash
npm run dev --prefix frontend
```

Instalação das dependências, uma vez:

```bash
pip install -r backend/requirements.txt && npm install --prefix frontend
```

O Vite faz proxy de `/api` para o backend, então não há CORS no caminho. A
documentação interativa da API fica em <http://localhost:8000/docs>.

### Como o lançador desliga os servidores

Fechar a janela no **X** manda `CTRL_CLOSE_EVENT`, e o Windows dá poucos
segundos antes de encerrar o processo — muitas vezes o `taskkill` do
encerramento não chega a rodar, e uvicorn e node ficam segurando 8000 e 5173.
Na vez seguinte o lançador acusaria "porta em uso".

Por isso o lançador se coloca dentro de um **Job Object** com
`JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`: todo processo que ele criar já nasce
membro, e quem garante a limpeza passa a ser o sistema operacional. Testado
matando o lançador à força — as duas portas ficam livres.

> Anexar os *filhos* ao job depois do `Popen` não funciona: é uma corrida, e o
> `cmd.exe` do backend já tinha criado o uvicorn antes da associação. Anexar o
> próprio lançador elimina a janela de corrida.

---

## Fluxo

1. Você digita a string de busca e clica em **Buscar no Scopus**. A busca traz
   **todos** os resultados da query — não há campo de máximo.
2. O backend pagina a Scopus, grava a **resposta bruta** em
   `dados/respostas_scopus/busca_<carimbo>.json` e persiste os artigos.
3. O OpenAlex preenche abstract e keywords por DOI (ver nota abaixo).
4. Os artigos aparecem na listagem, **15 por página**, ordenados por citações.
   A lupa 🔍 abre um modal com abstract, palavras-chave, veículo, tipo e DOI.
5. **Baixar pendentes** dispara o download em background dos que ainda não
   foram tentados. A tela atualiza a barra de progresso enquanto roda e para de
   consultar quando termina.
6. Artigos com PDF ganham o botão **Abrir PDF**, servido pelo backend inline.

A busca e o download são passos separados de propósito: você vê o que veio
antes de gastar tempo de rede baixando.

---

## Linhas de pesquisa

Cada busca no Scopus cria uma **linha de pesquisa** nova. As anteriores não são
descartadas: ficam no banco com os artigos, os PDFs e as respostas delas.

O painel **Linhas de pesquisa**, logo abaixo do formulário, lista todas com
data, número de artigos, PDFs baixados e respostas escritas. **Abrir** troca a
listagem para aquela linha; **Apagar** remove a linha inteira.

Apagar leva junto os artigos, as respostas e os PDFs **daquela** busca — a
confirmação diz os números antes. Não pode ser desfeito.

> A exclusão apaga apenas os arquivos registrados em `pdf_caminho` dos artigos
> da busca. Ela **nunca varre** `dados/pdfs/`: a pasta pode conter PDFs que você
> colocou ali à mão, e um `glob` levaria esses junto.

Uma linha com download em andamento não pode ser apagada (`409`) — espere o
lote terminar.

### Filtros

Quatro, combináveis: **título**, **download** (baixados / não baixados),
**paywall** (com / sem) e **análise** (analisados / não analisados). Trocar
qualquer um volta para a primeira página.

### Ordenação

Citações (padrão), ano decrescente, ano crescente ou título. Toda ordenação
termina desempatando por `id` — sem isso, artigos empatados no mesmo ano
podem repetir ou sumir entre páginas consecutivas.

### Os botões de download

| Botão | O que processa |
|---|---|
| **Baixar pendentes** | Todos os que nunca foram tentados (status `pendente`) |
| **Baixar [N] pendentes** | Só os N primeiros pendentes, na ordem da listagem |
| **Tentar novamente** | Os que ficaram como `paywall`, `landing` ou `erro` |
| **Baixar** (na linha) | Só aquele artigo |
| **Anexar PDF** (na linha) | Vincula um PDF do seu computador |

A separação do "tentar novamente" existe porque refazer os `paywall` custa
várias requisições por artigo para reconfirmar o que já se sabe. Ele só
aparece quando há o que retentar.

Cada linha com PDF baixado tem **Abrir PDF** (abre em nova aba), **⬇** (salva
o arquivo no computador) e **📎** (substitui por outro PDF).

### Anexar PDF manualmente

O botão **Anexar PDF** de cada linha abre o seletor de arquivos e vincula o PDF
escolhido ao artigo: o status vira `baixado`, a fonte fica como `manual` e o
arquivo é copiado para `dados/pdfs/` com o mesmo padrão de nome dos automáticos.

É o caminho para os ~80% que a resolução automática não alcança — artigo sob
paywall que você baixa pelo acesso da universidade e sobe aqui.

O backend confere a assinatura `%PDF` no **conteúdo**, não no nome nem no
`Content-Type`: renomear um `.docx` para `.pdf` é recusado com 415. O limite é
150 MB, e a gravação usa arquivo `.parcial` renomeado só no fim, para que um
envio interrompido não deixe um PDF truncado no lugar.

---

## Tema

O seletor no topo tem três estados: **claro**, **escuro** e **seguir o
sistema** (padrão). A escolha fica no `localStorage` e é aplicada por um script
no `index.html` **antes** do React montar — sem isso a página apareceria no tema
do sistema por um instante antes de trocar.

---

## Perguntas de pesquisa

O botão **Perguntas de pesquisa**, no topo, abre um drawer para criar, editar
e apagar as perguntas da sua revisão. Elas são globais: valem para todo artigo,
inclusive os de buscas futuras.

O botão **Perguntas** de cada linha leva para `/artigos/<id>/perguntas`, onde
todas as perguntas ativas aparecem com um campo de texto para a resposta. As
respostas são gravadas sozinhas cerca de 1 s depois que você para de digitar.

### A marca "Analisado"

Um artigo ganha a etiqueta **Analisado** quando **todas** as perguntas ativas
têm resposta preenchida — venha ela de você ou da IA. Resposta só com espaços
não conta. A data em que ficou completo fica em `analisado_em`.

A flag é gravada na tabela (para dar filtro e contagem em SQL), mas é
**derivada**: precisa ser recalculada quando as respostas ou as perguntas
mudam. Como as perguntas são globais, cadastrar a 9ª faz todo artigo que estava
completo com 8 voltar a ficar incompleto — e uma flag que não acompanhasse isso
mentiria justamente ao dizer o que ainda falta ler.

Por isso o recálculo vive num lugar só (`servicos/estado_analise.py`) e é
chamado ao salvar resposta, ao analisar com IA, e ao criar, arquivar, reativar
ou apagar uma pergunta. Além disso roda na **subida do servidor**: se algum
caminho novo esquecer de chamar, o próximo restart conserta.

Apagar uma pergunta apaga junto as respostas dela em **todos** os artigos — a
confirmação avisa. Para tirar uma pergunta de circulação sem perder o que já
foi escrito, use `PATCH /api/perguntas/<id> {"ativa": false}`.

### Analisar com IA

O botão **Analisar com IA**, na tela de perguntas do artigo, manda o PDF e as
perguntas ativas para o Claude numa única chamada e grava as respostas.

**Nada é substituído.** O texto da IA entra abaixo do que você já escreveu,
sempre marcado com `I.A:`:

```
Minha leitura: o setup não fica claro na seção 4.

I.A: Sim, os experimentos usam um Meta Quest 2.
Evidência: "participants wore a Meta Quest 2 headset" (p. 7)
```

Rodar de novo acrescenta outro bloco `I.A:` — não sobrescreve o anterior.

Quando o artigo não trata do que a pergunta pede, o modelo é instruído a dizer
isso e marcar confiança `nao_encontrado`, em vez de arriscar um palpite
plausível. Um "não aborda" correto é o que aponta lacuna na literatura; um
palpite contamina a matriz de síntese.

A saída vem por *tool use* com `strict: true`, não por texto livre — parsear
texto para casar resposta com pergunta poria a resposta da pergunta 3 no campo
da 5, erro que passa despercebido.

#### Dois modos, escolhidos por `MODO_ANALISE` no `.env`

| Modo | Como funciona | Custo | Requisito |
|---|---|---|---|
| `claude_code` (padrão) | Invoca a CLI do Claude Code em modo headless, com o **seu login** | já incluso na assinatura | CLI instalada e logada |
| `api` | Chama a Anthropic API direto | ~US$ 0,15/artigo | `ANTHROPIC_API_KEY` |

Para o modo padrão, uma vez só:

```bash
npm install -g @anthropic-ai/claude-code
```

Depois rode `claude` uma vez num terminal para fazer login com sua conta.

O modo `api` existe para processar o acervo em lote sem ninguém na frente —
é a única das duas rotas que roda desacompanhada.

**Por que sem `--bare`:** o modo bare acelera a partida da CLI, mas
[não lê as credenciais OAuth](https://code.claude.com/docs/en/headless) —
exigiria `ANTHROPIC_API_KEY` e derrubaria o motivo de usar a assinatura. O
preço é uma partida mais lenta.

**Por que `--allowedTools "Read"` e `--permission-mode dontAsk`:** em `-p` a
sessão começa no modo Manual. Sem liberar Read explicitamente, a leitura do PDF
pararia num pedido de permissão que ninguém vai responder, e o processo ficaria
pendurado até o timeout.

**Por que o prompt vai por STDIN, não em `-p "<prompt>"`:** no Windows a CLI é
um `claude.CMD`, e o `cmd.exe` **trunca um argumento na primeira quebra de
linha**. Com o prompt em argv, a sessão recebia só a primeira linha, ignorava o
PDF e as perguntas, e respondia conversando. Pelo stdin o texto chega inteiro.

**Por que `--disallowedTools` e `--strict-mcp-config`:** as definições das
ferramentas que a análise não usa custavam 13k tokens de entrada por invocação
(42k → 29k, medido). Ignorar os servidores MCP do ambiente torna o resultado
independente do que está configurado na máquina.

#### Medido numa execução real

Um artigo de 1,1 MB, 8 perguntas: **27 segundos**, ~91k tokens de entrada,
US$ 0,27 de custo estimado. O grosso da entrada é o contexto que o Claude Code
carrega por invocação — o preço de usar a assinatura em vez da API. Numa conta
Pro esse valor não é cobrado, mas consome da sua franquia de uso.

Requisitos comuns aos dois modos: o PDF baixado ou anexado e ao menos uma
pergunta cadastrada. O botão fica desabilitado dizendo o que falta, e a tela
mostra o passo a passo quando o pré-requisito do modo não está atendido.

> A IA sugere; ela não decide. Revise cada resposta antes de levar para a
> dissertação — é o que a banca vai cobrar.

---

## Síntese da revisão

A página **Síntese da revisão** (link no topo da listagem, ou `/sintese`) mostra
**uma pergunta por vez**: o enunciado no topo, e abaixo a resposta de cada
artigo a ela. Navegue com as setas ← →, pelos números, ou pelas setas do
teclado — que ficam inertes enquanto o foco está num campo de texto.

Comparar 8 perguntas × N artigos numa grade só exige rolagem nos dois eixos e
perde o contexto da coluna. Uma pergunta por vez é a leitura que serve para
escrever: você lê o que todos os artigos dizem sobre *um* ponto.

Dá para filtrar por linha de pesquisa, alternar entre "só analisados" e "todos",
e **exportar em CSV** (com BOM, para o Excel abrir os acentos certos).

### Perguntar sobre o conjunto

O campo abaixo da matriz manda **a matriz** — não os PDFs — para o Claude, com
quatro perguntas prontas voltadas a escrever um projeto de pesquisa: lacunas e
contribuições, panorama das estratégias, rigor experimental, contradições.

O prompt instrui o modelo a citar quais artigos sustentam cada afirmação, a
distinguir o que a matriz mostra do que ele está inferindo, e a lembrar que
**uma ausência na matriz pode ser limite do recorte da busca**, não da
literatura. As consultas ficam salvas: a resposta é material de trabalho, não
resultado descartável de tela.

O prompt também marca a origem de cada resposta (escrita por você, extraída por
IA, ou as duas), para o modelo não tratar sugestão de máquina com o mesmo peso
da sua leitura.

O histórico de consultas é **paginado**, uma por vez, com as mesmas setas e
números da matriz. Uma resposta passa de 4 mil caracteres; empilhar todas na
mesma tela deixava a página com metros de rolagem.

A resposta é renderizada como Markdown (títulos, listas, negrito, tabelas). O
`react-markdown` monta elementos React em vez de injetar HTML, e **não**
interpreta HTML cru sem o plugin `rehype-raw` — o que importa aqui, já que o
texto é produzido por um modelo lendo PDFs de terceiros.

> As sessões headless rodam de um **diretório neutro fora do projeto**. Rodando
> na raiz, a CLI carrega a auto-memória daquele caminho, e anotações de
> desenvolvimento entravam no contexto da revisão. Foi medido: uma resposta de
> síntese chegou a citar o roadmap do próprio sistema.

---

## Situações do PDF

Cada artigo tem uma flag `baixado` e um estado mais detalhado:

| Estado | O que significa |
|---|---|
| `baixado` | PDF salvo em `dados/pdfs/`, validado pelos *magic bytes* |
| `paywall` | Nenhuma versão aberta encontrada — precisa de upload manual |
| `landing` | Há versão aberta, mas só a página do artigo, sem link direto de PDF |
| `erro` | O link prometia PDF e o download falhou (WAF da editora, geralmente) |
| `pendente` | Ainda não foi tentado |

Na listagem, `paywall` e `landing` aparecem juntos como paywall — do ponto de
vista de quem vai ler, o efeito é o mesmo: o PDF não veio sozinho.

A distinção entre `landing` e `baixado` não é cosmética. O diagnóstico inicial
media 47% de resolução porque contava página de artigo como PDF; a taxa real
de arquivo em disco é ~20%. Nenhum resolvedor tenta contornar paywall.

---

## Nota sobre a chave do Scopus

O diagnóstico (`backend/ferramentas/diagnostico_viabilidade.py`) mostrou que
esta chave **não tem direito a `view=COMPLETE`** — a Scopus responde 401 com
*"not authorized to access the requested view"*. Na prática a busca volta com
0% de abstract e 0% de keywords.

Por isso a busca roda em `STANDARD` e o **OpenAlex** preenche abstract e
keywords por DOI: é gratuito, não exige chave, não consome quota e ainda traz
conceitos que a `view=COMPLETE` não traria. Se um dia a assinatura liberar
`COMPLETE`, basta definir `SCOPUS_VIEW=COMPLETE` no `.env`.

---

## Limites da chave do Scopus

Além da falta de `view=COMPLETE`, esta chave tem dois limites que o código
contorna sozinho:

- **Páginas de no máximo 25 resultados.** Pedir mais devolve
  `400 Exceeds the maximum number allowed for the service level`. O código
  tenta 200, depois 100, depois 25, e fica no primeiro que a chave aceitar —
  assim uma assinatura melhor passa a gastar menos quota sem mexer no código.
- **Parâmetro `cursor` restrito** (`403 Use of the cursor parameter is
  restricted`). A paginação usa offset, que a Scopus limita a **5.000
  resultados por busca**. Uma query acima disso precisa ser fatiada — por ano,
  por exemplo.

A quota é de cerca de 20.000 requisições semanais, ou seja ~1 requisição a cada
25 artigos recuperados. OpenAlex, Unpaywall e arXiv são gratuitos e não contam
nessa quota.
