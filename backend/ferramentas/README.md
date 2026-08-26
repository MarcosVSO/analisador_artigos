# Etapa 0 — Validação de viabilidade

Diagnóstico que roda **antes** de escrever qualquer código do sistema. Não grava
no banco, não faz parte do produto final. Existe para responder duas perguntas
cujas respostas mudam a arquitetura das etapas seguintes:

1. A chave da Scopus entrega metadados úteis — em especial, **abstract**?
2. Que fração dos artigos da busca dá para **baixar em PDF automaticamente**?

## Como rodar

```bash
pip install -r requirements.txt
```

Copie `.env.example` para `.env` e preencha:

| Variável | Onde conseguir | Obrigatória |
|---|---|---|
| `SCOPUS_API_KEY` | [dev.elsevier.com/apikey/manage](https://dev.elsevier.com/apikey/manage), login institucional → *Create API Key* | sim |
| `SCOPUS_INSTTOKEN` | [suporte Elsevier](https://dev.elsevier.com/support.html) — só necessário fora da rede da universidade | não |
| `CONTACT_EMAIL` | um e-mail seu real; o Unpaywall exige, o OpenAlex recomenda | sim, na prática |
| `SCOPUS_QUERY` | **sua** string de busca, na sintaxe do Scopus | sim |

> A chave fica só no `.env`, que está no `.gitignore`. Não coloque credencial
> em nenhum outro arquivo do repositório.

```bash
python etapa0/validar.py
```

Opções: `--query "..."` e `--amostra 25` sobrescrevem o `.env`;
`--sem-download` resolve as URLs sem baixar PDF de fato.

## O que cada teste responde

| Teste | Pergunta | Consequência se falhar |
|---|---|---|
| **A** — autenticação e quota | A chave funciona? Quanta quota resta? | Se falhar, o projeto troca a fonte de descoberta para OpenAlex |
| **B** — `view=COMPLETE` | A assinatura libera abstract e keywords na busca? | Sem isso, os abstracts precisam vir do OpenAlex ou de 1 requisição extra por artigo |
| **C** — busca real | Quantos artigos existem? Os campos vêm preenchidos? | Cobertura baixa de DOI → dedup por título+ano na Etapa 1 |
| **D** — resolução de PDF | Qual a taxa de download automático? | É o número que dimensiona a Etapa 3 |

A saída bruta vai para `etapa0/resultado.json` (fora do git), incluindo a lista
de artigos da amostra e o motivo de cada PDF não resolvido.

## Custo de quota

Uma execução gasta **3 requisições** da quota do Scopus (testes A, B e C).
A quota semanal típica da Search API é de 20.000, então dá para rodar à
vontade enquanto você ajusta a string de busca.

O teste D não toca no Scopus, exceto quando um DOI é da Elsevier (prefixo
`10.1016/` e afins) — aí faz uma chamada à ScienceDirect por artigo.

## Interpretando o resultado do teste D

| Taxa | Leitura | Efeito na Etapa 3 |
|---|---|---|
| ≥ 60% | boa | resolvedor completo se paga; fila manual administrável |
| 30–60% | razoável | faça a Etapa 3, mas a tela de upload manual é parte central do fluxo |
| < 30% | ruim | reduza a Etapa 3 a só Unpaywall e invista no upload manual em lote |

Nenhum resolvedor tenta contornar paywall. Artigo sem versão aberta é marcado
como `paywall` e vai para a fila de upload manual — você baixa pelo acesso da
universidade e sobe pelo sistema.
