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
    esquemas.py           contratos de entrada/saída da API
    main.py               aplicação FastAPI
    rotas/
      buscas.py           executar busca, progresso, disparar download
      artigos.py          listagem filtrada, download por artigo, PDF
      perguntas.py        perguntas de pesquisa e respostas por artigo
    servicos/
      scopus.py           cliente da Scopus Search API
      openalex.py         enriquecimento de abstract e keywords
      resolvedor_pdf.py   cadeia de resolução de full-text
      busca.py            orquestra Scopus → arquivo bruto → OpenAlex → banco
      download.py         download em background com pool de threads
  ferramentas/
    diagnostico_viabilidade.py   diagnóstico da API (ver ferramentas/README.md)

frontend/                 React + Vite + TypeScript
  src/
    App.tsx               rotas
    api.ts                cliente HTTP
    tipos.ts              tipos compartilhados
    paginas/
      PaginaListagem.tsx  busca, filtros e tabela de artigos
      PaginaPerguntas.tsx respostas de um artigo
    componentes/          formulário, progresso, tabela, modal, drawer

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

Backend (porta 8000):

```bash
pip install -r backend/requirements.txt
```

```bash
python -m uvicorn app.main:app --reload --port 8000 --app-dir backend
```

Frontend (porta 5173), em outro terminal:

```bash
npm install --prefix frontend && npm run dev --prefix frontend
```

Abra <http://localhost:5173>. O Vite faz proxy de `/api` para o backend, então
não há CORS no caminho. A documentação interativa da API fica em
<http://localhost:8000/docs>.

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

### Filtros

Três, combináveis: **título**, **download** (baixados / não baixados) e
**paywall** (com / sem). Trocar qualquer um volta para a primeira página.

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

## Perguntas de pesquisa

O botão **Perguntas de pesquisa**, no topo, abre um drawer para criar, editar
e apagar as perguntas da sua revisão. Elas são globais: valem para todo artigo,
inclusive os de buscas futuras.

O botão **Perguntas** de cada linha leva para `/artigos/<id>/perguntas`, onde
todas as perguntas ativas aparecem com um campo de texto para a resposta. As
respostas são gravadas sozinhas cerca de 1 s depois que você para de digitar.

Apagar uma pergunta apaga junto as respostas dela em **todos** os artigos — a
confirmação avisa. Para tirar uma pergunta de circulação sem perder o que já
foi escrito, use `PATCH /api/perguntas/<id> {"ativa": false}`.

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
