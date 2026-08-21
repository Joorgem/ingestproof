> Copied on 2026-08-20 from `docs/superpowers/specs/2026-08-18-ingestproof-design.md`.
> The origin is the private planning repository; changes land there first. Section 0 of
> this document is the record of what v1 got wrong, and it is kept deliberately.

# Design — `ingestproof`: o contrato de ingestão, e a prova de que o parse não mentiu

**Data:** 2026-08-18 · **v2**, reescrita depois de revisão adversarial
**Status:** Aguardando revisão do Jorge
**Vaga alvo:** 102697 — Sr. Data Engineer (`docs/102697-sr-data-engineer.md`)
**Medições:** `docs/superpowers/research/ingestproof-measurements.md` — **nenhum número deste documento pode ser citado sem estar lá**
**Fases:** P0–P6. O prefixo `P` existe para não colidir com as fases F0–F7 do flagship, que este documento também referencia.

---

## 0. O que mudou da v1, e por quê

A v1 propunha uma **biblioteca de fidelidade de ingestão** — um diferencial de dois parsers, sozinho. Ela passou por uma revisão adversarial de dez agentes que produziu **nove bloqueadores e trinta e dois achados altos**, e refutou **as quatro alegações estruturantes**. Três achados mataram o desenho:

**A extração era falsa.** `src/opl/bronze/reader.py` tem 278 linhas brutas e **67 de código, das quais 39 são despacho sobre o catálogo do flagship**. O motor proposto não existia em lugar nenhum — grep por `duckdb`, `byte_offset`, `differential` sobre 27.106 linhas: zero. `git log --stat` mostraria ~100% código novo sob um documento que dizia "módulo extraído".

**O Nível 2 era enxerto, e tinha quatro bloqueadores medidos.** O diferencial contra a tabela Delta *pousada* gera **1% de falso positivo com zero dano real**, porque bronze é o parse **menos** os rejeitados pelo gate. Não há chave de alinhamento do lado Delta — só `_source_file`. O serverless proíbe o modelo de execução (RDD banido, UDF com teto de 1 GB, sem cache). E `multiLine=true` força uma tarefa por arquivo.

**E a régua estava errada.** A lente de contratação mediu: o Nível 2, como escopado, ficava **abaixo do que o flagship já publica** — 20 YAMLs de job, condition tasks, guard de proveniência, gate de DQ, dashboard. A parte vendida como "é aqui que vira sênior" mostrava menos do que já existe público.

**E um achado que expôs um erro de processo meu.** A decisão de 22/07 nomeia literalmente *"extrair o gerador chaos-aware (ou framework de contratos+quarentena) para PyPI"*. A v1 propunha uma terceira coisa e afirmava estar honrando aquela decisão. A troca nunca foi argumentada — passou despercebida por mim e pelo Jorge por seis commits.

**A v2 é a fusão**, decidida pelo Jorge em 18/08: o framework de contratos+quarentena é o chassi, e o diferencial de fidelidade é o check mais distintivo dentro dele. Nada da pesquisa se perde — o diferencial deixa de ser *o produto* e vira *o check que ninguém mais tem*.

---

## 1. Contexto e objetivo

### A lacuna, dita com precisão

O anúncio pede:

> *"Build reusable data frameworks, libraries, and reference architectures to accelerate team productivity and platform adoption."*

**A v1 dizia que este era "o único requisito sem artefato". Era falso** — IaC, streaming e cataloging também estão descobertos, e o flagship já *é* um wheel versionado que todo job do Databricks instala.

O que sobrevive, e basta: **a biblioteca do flagship é inédita, não documentada como reutilizável, e acoplada a um domínio.** Ninguém fora daquele repositório consegue instalar. Nada nela é enquadrado como framework. É a diferença entre ter escrito uma biblioteca e ter **publicado** uma.

O segundo objetivo é de método: demonstrar **loop engineering** com gates mecânicos, num projeto onde isso é seguro. O flagship não pode demonstrar — o histórico dele já mostra o outro método, e é código maduro com risco de integridade de dado, que o próprio método manda **não** colocar em loop cego.

### O que este documento NÃO é

Não é um segundo lakehouse. É a fatia de **biblioteca extraída** que a decisão de 22/07 já previa (os 10% da composição de portfólio) — agora com o candidato que aquela decisão nomeou.

---

## 2. A tese

> **Uma ingestão bronze é um contrato. Declara uma vez e sai o schema, as regras de qualidade, a quarentena, a promoção e o wiring do job — mais um check de fidelidade que prova que o parse não mentiu.**

E a frase que a pesquisa comprou, agora honesta:

> Toda ferramenta de qualidade valida **o dado que você recebeu**. Aqui o contrato também cobre **se o que você recebeu é o que foi mandado** — e isso só é possível porque a mesma declaração é dona do parse, do gate e da quarentena.

### Por que a fusão resolve o que o diferencial sozinho não resolvia

Os quatro bloqueadores do Nível 2 existiam **porque o diferencial era externo ao gate**. Um framework que é dono do contrato, do gate e da quarentena já sabe o que é `_batch_id`, o que foi promovido e o que foi quarentenado. O alinhamento deixa de ser problema externo e vira competência interna.

---

## 3. O que a pesquisa matou — e por que vai para o README

Esta seção é o artefato mais forte do repositório. Publicar os próprios becos sem saída, com medição, é o que separa sênior de júnior. **Nenhum item pode ser silenciosamente removido.** Números completos em `ingestproof-measurements.md`.

**3.1 — "Ninguém valida origem × tabela" é falso.** Reconciliação source-to-target é categoria nomeada com ~12 implementações, incluindo **duas do Databricks Labs**: DQX `compare_datasets` e Lakebridge reconcile. A frase "ninguém faz isso" está **proibida** em todo artefato deste projeto.

**3.2 — Round-trip byte a byte é insound.** RFC 4180 torna aspas opcionais → falso positivo em CSV válido. E a correção óbvia cria ponto cego: dano de **re-segmentação** round-trippa byte-idêntico. ~~medido em 4 de 8 eixos~~ — **essa contagem não tem derivação nas medições; ver §12.7. Não citável até ser re-derivada**, e por isso saiu do README, cuja regra é que todo número dele seja encontrável em `measurements.md`.

**3.3 — Conservação escalar é cega onde importa.** Dos 459 danos reais do incidente do `escape`, **456 preservam contagem de campo, de linha, bytes totais E digest do payload**.

**3.4 — O problema já tem métrica formal.** Pollock, VLDB 2023. DuckDB lidera com 9,961.

**3.5 — Existe linha de base gratuita, e ela abre o README.** ~~Um script de 12 linhas de DuckDB pega os três incidentes com controle limpo.~~ **FALSIFICADO em 19-20/08/2026 — ver §12.6 das medições.** Medido: o DuckDB 1.5.5 pega **1 dos 3**, e os outros dois ele parseia **corretamente** — são CSV válido, e o dano foi do leitor de produção, não do arquivo. Um parser correto não tem o que rejeitar e não tem contra o que comparar. A conclusão da seção fica **mais forte**, não mais fraca: a lacuna medida de 2 em 3 é exatamente a classe que exige dois parsers em vez de um. *"Eu medi a alternativa gratuita e aqui está a diferença"* é sinal sênior; *"ninguém faz isso"* morre em trinta segundos.

**3.6 — E o leitor de referência não entrega posição de byte para o que importa.** ✔ Re-probado: o `reject_errors` do DuckDB só popula para linhas **rejeitadas**; a linha do incidente ele parseia limpa e não emite posição. Para o que ele *rejeita* há posição — a saída do baseline diz `line=4 col=3`. Então o limite não é ausência de posição: é que **não há posição para as linhas que ele aceitou**, que é onde o dano destes incidentes mora. **DuckDB é oráculo de VALOR, e de posição só sobre o que rejeita.**

---

## 4. Prior art — tabela obrigatória do README

Cada uma entra com o que **deixa passar**. Omitir qualquer uma é o defeito; incluir os próprios contraexemplos é o que dá credibilidade.

| ferramenta | o que faz | o que deixa passar |
|---|---|---|
| **Databricks Labs DQX** | regras de qualidade + `compare_datasets` em Databricks | compara dois DataFrames — ambos já parseados, defeito de parse cancela dos dois lados |
| **Databricks Labs Lakebridge** | reconcilia origem relacional × Databricks | fonte relacional apenas; não aceita arquivo |
| **Google DVT** | arquivo × tabela | lê com `pandas.read_csv(path)` puro, sem dialeto; row-hash não suportado para arquivo |
| **datacompy** | comparação DataFrame × DataFrame com relatório de diferenças | os dois lados já vêm parseados, e ele não opina sobre como foram lidos |
| **Frictionless** | checksum/bytes/linhas/campos do arquivo | prova que o arquivo é o esperado, não que o parse o preservou |
| **Great Expectations / dbt-expectations / Deequ** | tabela, e cross-table | mesma anulação de defeito compartilhado |
| **Soda** | recon entre duas relações | recon não está no pacote OSS |
| **dlt / Pandera** | contratos de schema na ingestão | contrato de tipo e forma, não de fidelidade de parse |
| **DuckDB** `strict_mode` + `store_rejects` | rejeições do próprio parse do DuckDB | descreve o parse do DuckDB, não a tabela que ficou |
| **Pollock** (VLDB 2023) | métrica formal arquivo × carga | precisa de ground truth; é benchmark, não gate |

**A frase que mata a família cross-table inteira:** todas comparam duas coisas **já parseadas**, então defeito de parse compartilhado se cancela nos dois lados — que é exatamente o incidente do `multiLine`, onde a contagem de linhas fechou em volta do dano.

**O que não está empacotado em lugar nenhum:** uma declaração única que gera schema + regras + quarentena + promoção + job **e** carrega um check de fidelidade contra os bytes de origem.

---

## 5. Escopo — três camadas

### Camada 1 — o contrato declarativo (o chassi)

Origem: `src/opl/bronze/registry.py` (769 linhas), `rules.py` (481), `rule_predicates.py` (428), `contracts/catalogue.py` (134) do flagship — generalizados para fora do domínio CNPJ.

- Uma **declaração por tabela**: nome, contrato, tripla staging/bronze/quarentena, modo de landing, prefixo, constraints.
- **Guards que recusam no import** — contrato inexistente, prefixo que não casa com grupo de arquivo, tabela sem job.
- **Regras de qualidade derivadas do contrato**, como `(nome, callable → Column)`: a *definição* é Python puro; só a *avaliação* toca no Spark.
- Promoção fail-closed e quarentena por `_batch_id`.

**Propriedade que torna isso loop-safe e que vem de graça:** a camada de declaração **não importa Spark, e não pode** — o flagship tem um teste segurando isso (`test_the_registry_still_imports_where_pyspark_is_not_installed`). O anel interno do loop roda inteiro sem JVM.

### Camada 2 — o check de fidelidade (o distintivo)

Diferencial de valor entre dois parsers, contra um **dialeto de origem declarado**.

- O dialeto é **entrada obrigatória, nunca inferida**. A biblioteca se recusa a rodar sem ele. Contrato numa frase: *"Você afirma o que o produtor escreveu. Nós provamos que o leitor leu aquilo."*
- **DuckDB como oráculo de valor** (não de posição — §3.6). Versão pinada.
- Localização por **(índice de registro, índice de campo)**. Posição de byte é melhoria opcional da Camada 3, não requisito.
- **Resincronização obrigatória:** medido, um registro com quebra de linha embutida faz o Spark emitir 1.001 linhas para 1.000 registros, e um `zip` posicional reporta ~500 divergências para 1 dano. Depois de divergir, reancorar em K registros byte-idênticos consecutivos e reportar **span de dano limitado**.
- **Alvo de comparação: `promote ∪ quarantine` de um mesmo `_batch_id`, ou a staging antes do gate. Nunca a bronze pousada** — medido, 1% de falso positivo com zero dano real.

### Camada 3 — precisão e alcance (cortável, nesta ordem)

1. Tokenizador de span próprio, para localizar por byte.
2. Segundo formato de origem (JSON Lines) pela interface de plugin. **O entregável não é "funciona em dois formatos" — é o `git show --stat` do commit que adiciona o segundo: +N arquivos, 0 modificados.**

---

## 6. O corpus de regressão

Oito incidentes reais do flagship, classificados por **mecanismo de reprodução**, não pela plataforma onde aconteceram.

- **Camada A — Python puro + stdlib** (anel interno): `SystemExit` sob IPython (é bug do IPython, não do Databricks); truncamento do `files.upload` do sdk 0.40 (reproduzido e bissectado contra socket local — 229.376 bytes perdidos em silêncio na 0.40, zero na 0.42.0); `COUNT(DISTINCT)` derrubando NULL.
- **Camada B — Spark OSS via `pip install pyspark`** (anel interno): `multiLine=false` partindo registro; `escape` ausente engolindo delimitador; schema explícito + PERMISSIVE descartando campo extra **enquanto o FAILFAST no mesmo arquivo levanta erro** — o parser sabia e descartou a informação por padrão.
- **Camada C — precisa de workspace** (documentação, nunca gate): `_rescued_data` não popular; retry de `INTERNAL_ERROR`; o log de deploy. Entram como **script de reprodução com saída registrada**, rotulados como reprodução, não gate.

O retry de `INTERNAL_ERROR` é reescrito como **invariante**, não reprodução: o teste é *"rodar o writer duas vezes deixa a tabela idêntica"*, local com Delta OSS.

**Provisionamento do corpus grande** — a v1 não tinha resposta e isso bloqueava P1. Ver ASM-6.

---

## 7. O harness do loop

### 7.1 Os arquivos

| arquivo | papel | quem escreve |
|---|---|---|
| `prompt.md` | instrução fixa de toda volta | humano, congelado |
| `.spec/` | critérios de aceite com id | humano, congelado |
| `TASKS.md` | fila, com critério mecânico por item | humano, congelado |
| `AGENTS.md` / `CLAUDE.md` | como buildar e testar | humano |
| `LOOP.md` | estado atual | o harness |
| `$LOOP_HOME/iterations.jsonl` | ledger, **fora da árvore de trabalho** | o harness |

### 7.2 Os anéis

- **Interno** (segundos, toda volta): `ruff`, `mypy`, `pytest`, Hypothesis, corpus A+B. **Sem JVM, sem Spark** — a Camada 1 garante isso.
- **Noturno** (minutos, **Linux apenas**): mutação, rastreabilidade, cobertura em diff, gate de regime de tamanho, testes de Spark.
- **Externo** (raro, gate humano): release no PyPI; PR de adoção no flagship; a prova no workspace.

### 7.3 Caminho gravável — a v1 era autocontraditória

A v1 congelava `tests/**` inteiro **e** mandava o agente editar teste (fixar `@example`, matar mutante). Deadlock na primeira falha de propriedade.

**Allowlist, aplicada por hook `PreToolUse` e re-conferida no CI:** o agente escreve **somente** em `src/**`, `tests/unit/**`, `tests/property/**`, `docs/**`, `TASKS.md` não — só `LOOP.md`.

**Congelados** (SHA-256 conferido no CI a cada volta): `tests/acceptance/**`, `.spec/**`, `TASKS.md`, `pyproject.toml`, `.github/**`, `.gitattributes`, o gerador de fixtures, e a configuração de cobertura e mutação.

**Escapes que a v1 deixava abertos e que a allowlist fecha:** `conftest.py` na raiz (provado que transforma suíte de aceite vermelha em verde), `test_*.py` fora de `tests/`, `pytest.ini`/`tox.ini`, e os três formatos de pragma. `# pragma: no mutate`, `@pytest.mark.skip` e `xfail` exigem justificativa de uma linha, e a contagem vai no ledger.

**A configuração do hook vive em `~/.claude/settings.json`, fora do repositório** — dentro dele o agente poderia editá-la, e aí seria conselho, não bloqueio.

### 7.4 A volta é atômica

`git reset --hard` **não remove arquivo não rastreado** — o `conftest.py` órfão de uma volta morta sobrevive para a próxima. Toda volta começa com **`git reset --hard && git clean -fdx -e .venv`**, ou worktree descartável.

### 7.5 Três resultados, não dois

- **RED** — desfaz.
- **INDETERMINATE** — re-roda os testes do commit anterior contra o código novo; se o anterior também der vermelho, **o ambiente mexeu: para e chama**. Um vermelho só é INDETERMINATE quando o diff **não toca nada além de** `docs/**` e `LOOP.md` — a v1 dizia "código de produção" sem nunca definir, o que era carta de sair da cadeia.
- **TIMEOUT** — por teste, com `pytest-timeout`. Timeout em teste que passou na volta anterior sob o mesmo código é INDETERMINATE; caso contrário é RED.

### 7.6 Detector de travamento, com fechamento mecânico

Se N voltas passarem sem fechar tarefa, **para sozinho e escreve por quê**.

**Tarefa fechada tem definição externa ao agente:** o id de critério que ela nomeia sai de *não coberto* para *coberto* no relatório de rastreabilidade **E** o teste de aceite congelado que cita aquele id vai de vermelho para verde. O agente não pode fechar tarefa escrevendo no `TASKS.md`, porque ele não escreve lá.

### 7.7 Protocolo do Hypothesis

Perfil `ci`: `derandomize=True`, `database=None`. A semente é hash do código-fonte limpo do teste, então **renomear ou editar um property test re-sorteia o corpus** e um verde vira vermelho sem mudança de produção.

- Uma volta **não pode** editar corpo ou nome de property test no mesmo commit que muda produção. Vermelho depois de edição de teste é INDETERMINATE.
- Falhou propriedade? A única tarefa da volta é: fixar o contraexemplo como `@example(...)` em `tests/property/**`, corrigir o código, commitar. O `_clean_source` remove decoradores, então fixar `@example` **não** re-sorteia.

### 7.8 Gate de regime de tamanho — o anel interno não alcança este projeto

Medido: o buffer do Hypothesis é 8.192 bytes; pedindo até 5 MB, o **maior exemplo gerado foi de 32 bytes**. O corpus é medido em dezenas de milhões de linhas. *O anel interno é rápido e determinístico precisamente porque nunca entra no regime que a biblioteca policia.*

Fixtures grandes **geradas por script congelado**, cruzando 1 MiB, 4 MiB e 64 MiB. O teste afirma `os.path.getsize()` contra os três limiares **antes** de rodar o diferencial — senão encolher o gerador deixa o gate verde em dois segundos.

### 7.9 Gates: sinal e teatro

- **Mutação:** `mutmut` 3.7+, **só em Linux** (precisa de `fork`). Gate em **zero sobreviventes novos nas funções que a volta mudou**, nunca em score. E mutmut 3 só muta **dentro de funções** — constante em nível de módulo produz zero mutantes, então nenhuma constante nova em `src/**` sem teste que afirme o valor dela.
- **Rastreabilidade:** **OpenFastTrace 4.9.0**, que é **JAR de Java 17**, não pacote Python. Ids na gramática dele: `req~ac-02~1`. `Needs:` é **obrigatório** em todo item — item sem `Needs` é terminal e traça limpo, o que anularia o gate. E OFT **não** pega deriva de revisão sozinho (depende de alguém incrementar a revisão); o equivalente mecânico é o CI guardar SHA-256 do texto de cada critério.
- **Cobertura:** só em diff, com branch, configuração congelada.
- **Benchmark de wall-clock: não é gate.** Variância de runner engole o limiar. Throughput vai no ledger. E o piso de "150 MB/s" da v1 estava uma ordem de grandeza errado: **DuckDB em cp1252 mede ~15 MB/s single-threaded**, contra 121 em UTF-8.

### 7.10 O PR: o loop abre e conserta; o merge é humano

O loop abre, roda os gates, **espera o revisor automático concluir**, e resolve o que ele apontar. Não mergeia. `pending` e "rate limited" **bloqueiam**.

**Resolver tem check mecânico:** uma volta só marca achado como resolvido se o diff daquela volta tocar o arquivo e o intervalo de linhas que o achado cita. Sem isso, o agente fecha thread por GraphQL sem mudar código. Achados fechados sem hunk correspondente vão listados no corpo do PR como **dispensados, com justificativa**.

**Enquanto espera merge**, o loop puxa a próxima tarefa independente numa branch nova cortada da mesma base, e nunca abre um segundo PR que toque arquivo do PR aberto.

**Por que o revisor não aprova:** o defeito dominante deste trabalho é **defeito de plano** — na F1.4a do flagship, quatro só na Task 11, três dos quais nenhum teste pegaria. Revisor automático lê o diff; não pergunta se a tarefa era a certa.

### 7.11 O ledger sobrevive ao próprio loop

A v1 tinha um defeito circular: se o ledger é rastreado e a entrada RED está no commit, **desfazer o commit apaga o registro da volta desfeita**.

O ledger vive em **`$LOOP_HOME/iterations.jsonl`, fora da árvore**, escrito pelo harness e nunca pelo editor do agente. Cada entrada carrega o SHA-256 da anterior, então truncar ou reescrever é detectável. O `LOOP.md` no repositório é uma **renderização**, não a fonte.

Campos por volta: tarefa, id de critério, resultado (RED/GREEN/INDETERMINATE/TIMEOUT), tamanho do diff, custo, contagem de pragmas, e **`author`: `human` | `loop` | `loop-adjudicated`**. Esse último existe para o README publicar a **divisão medida** em vez de uma alegação sobre ela.

### 7.12 Manifesto do commit 1 — valores literais, sem invenção

A v1 mandava congelar o ambiente e não dizia com o quê. Um estranho teria que inventar seis decisões.

| item | valor |
|---|---|
| Python | **3.12** (`py -3.12` = 3.12.10 nesta máquina; o `python` padrão é 3.14 e **não** serve) |
| Gerenciador | **uv** + `uv.lock` |
| Build backend | **hatchling** |
| Layout | `src/ingestproof/` |
| Branch padrão | `main` — via `git init -b main`; o `init.defaultBranch` local é `master` |
| Repositório | `Joorgem/ingestproof`, público |
| `.gitattributes` | `-text` em `*.csv *.jsonl *.txt *.bin` sob `tests/fixtures/` |
| Engine de referência | `duckdb==1.5.5` |
| Rastreabilidade | OFT `4.9.0` (JAR + sha256), invocado por **`"$JAVA_HOME/bin/java"`** — verificado 19/08: `java` puro resolve 11.0.31, `$JAVA_HOME` resolve 17.0.19; os dois JDKs já estão na máquina |
| Env | `PYTHONHASHSEED=0`, `TZ=UTC`, `LC_ALL=C.UTF-8`, `CI=true` |
| Hypothesis | perfil `ci` registrado |
| Revisor | CodeRabbit, instalado em `Joorgem/ingestproof` — **gate humano, ver handoff** |

---

## 8. Quadro de segurança

1. **Sandbox.** O loop **não roda desassistido** na máquina do Jorge. P0–P1 rodam **atendidos** (`/loop` em sessão, Degrau 1). Desassistido exige container ou VPS. *A v1 dizia "nunca na máquina do Jorge" e no §9 descrevia exatamente isso — contradição corrigida.*
2. **Credencial de produção nunca entra.** A biblioteca não tem credencial por desenho.
3. **Git como checkpoint.** Branch própria, commit por volta verde.
4. **Teto de gasto** por volta e acumulado, no ledger.
5. **Gates de teste, tipo e lint**, com a configuração congelada e conferida por SHA-256.
6. **Hooks determinísticos.** Instrução em prompt é conselho; hook executa sempre.
7. **Escopo pequeno.** PR que cabe em revisão de 15 minutos.
8. **Databricks: nunca em modo desassistido.** *A v1 escrevia isto como absoluto, e assim proibia a própria fase que declarava obrigatória.* A regra real: **esta raia não toca no Databricks dentro do loop. A única exceção é a prova da P3 (AC-08b), executada manualmente pelo Jorge, fora do loop, com a raia do flagship parada** — a quota é por conta e derrubaria a F4/F5 de lá.
9. **Memória compartilhada:** só acrescentar bloco datado, nunca reescrever.

---

## 9. Onde roda

| degrau | o quê | quando |
|---|---|---|
| **1** | `/loop` em sessão, atendido | P0–P1 |
| **2** | headless local destacado, **em container** | quando o harness estabilizar |
| **3** | VPS Hetzner CX22 (Q-1b) | P5, opcional |

Degrau 2 exige container justamente porque o item 1 do §8 proíbe desassistido fora dele. `Dockerfile` entra no manifesto do commit 1 quando o degrau 2 começar.

Os testes de Spark rodam no **CI e no anel noturno**, nunca no anel interno e nunca na VPS — o KVM 1 tem 4 GB e o flagship já mediu Spark falhando com `BlockManager` a ~1,8 GB livres.

---

## 10. Ligação com o flagship — dito com honestidade

**Origem.** O termo é **"deriva de"**, não "extraído", e a distinção importa porque `git log --stat` vai contar a verdade:

- **Atravessa como código:** `registry.py`, `rules.py`, `rule_predicates.py`, `contracts/catalogue.py` — ~1.800 linhas, generalizadas para fora do domínio CNPJ. É extração de verdade.
- **Atravessa como dado:** o literal `CSV_DIALECT` (`contracts/cnpj_schemas.py:7-14`, 6 chaves das quais 4 usadas — precisa ser estendido com política de escape, separador de registro e semântica de vazio antes de servir).
- **É protótipo, e a v1 omitia:** `tests/bronze/test_reader_multiline.py::test_real_doubled_quote_records_match_rfc4180_field_for_field`. O flagship já rodou o diferencial contra `csv.reader` à mão, e foi assim que o incidente do `escape` apareceu. **É a prior art de casa, e ela vai citada pelo nome no README.**
- **É novo:** o descritor de dialeto, o diferencial e a resincronização.

**Adoção.** O PR no flagship troca a checagem à mão pelo pacote **no caminho de produção** — não apagando um teste. Ponto de inserção: entre `promote` e `reclaim_landing` em `bronze_cnpj_estabelecimentos_job.yml`, porque `reclaim_landing` apaga os CSVs de origem depois de promover.

**Sequenciamento — a v1 estava errada aqui.** Ela mandava esperar a F4 e a F5 do flagship. Medido: a F4 está na Task 5 de 8 e a F5 não começou, o que põe isso a 10–20 dias. **E a justificativa é empiricamente falsa: a F4 não toca nem `reader.py` nem `test_reader_multiline.py`.** Não há colisão a evitar.

**Prova mais barata, disponível no dia em que a P2 fechar:** rodar contra o que o flagship **já pousou** e publicar o resultado — achou ou não achou — como `docs/adoption-dry-run.md`. O PR de adoção deixa de ser bloqueador da narrativa.

---

## 11. Suposições e perguntas em aberto

### Suposições

- **ASM-1** — Nome `ingestproof`, livre no PyPI e no GitHub (conferido 18/08), e o Trusted Publisher já está configurado nele.
- **ASM-2** — Primeiro formato: CSV delimitado. Segundo: JSON Lines.
- **ASM-3** — Licença MIT.
- **ASM-4** — Repositório público desde o commit 1.
- **ASM-5** — A lista congelada do §7.3 vale desde o commit 1, e o hook vive fora do repositório.
- **ASM-6 — Provisionamento do corpus grande.** `Estabelecimentos6` **não entra em repositório nenhum**: são 14 GB git-ignored, e existem **dois** arquivos com esse nome (2026-06 com 366.882.667 B e 2026-07 com 368.109.911 B). A P0 entrega um **downloader commitado**, com URL da RFB, mês fixado e SHA-256 esperado. Ele roda no **anel noturno com cache**, nunca a cada volta, e nunca na VPS.

### Perguntas em aberto

- **Q-3** — A seção "How this was built" entra também no README do flagship? *Não bloqueia. Recomendação: sim — a velocidade e a prosa de lá já leem como assistidas, e não declarar lê pior que declarar.*
- **Q-4** — Reconciliar **4.753.435 vs 4.753.436**: a spec dizia 435, `src/opl/bronze/reader.py:65` diz "461 of 4,753,436". Um é registro, o outro provavelmente LF. *Bloqueia AC-02b, não a P0.*

---

## 12. Critérios de aceite

Gramática OFT: `req~ac-NN~1`. Todo item carrega `Needs: impl, utest`.

| id | critério | ring |
|---|---|---|
| **AC-01** | Uma tabela nova entra por **uma declaração** e sai com schema, regras, quarentena, promoção e YAML de job — sem editar nenhum módulo de execução. | interno |
| **AC-02a** | O diferencial detecta os três incidentes de CSV num corpus **gerado por script congelado**, com controle negativo limpo, no CI, em menos de um minuto. | interno |
| **AC-02b** | **Zero falso positivo** sobre o `Estabelecimentos6` real (mês e SHA-256 fixados por ASM-6), medido uma vez, com comando e saída commitados como evidência. **Não é gate de CI.** | noturno |
| **AC-03** | O relatório localiza cada dano por **(índice de registro, índice de campo)**. Posição de byte é da Camada 3 e não é exigida aqui. | interno |
| **AC-04** | A biblioteca **recusa** rodar sem dialeto de origem declarado, com mensagem que diz o porquê. | interno |
| **AC-05** | A taxa de falso positivo sob dialeto errado está medida **com denominador próprio** e publicada. *(A v1 reusava o denominador 459 de outro experimento.)* | noturno |
| **AC-06** | O veredicto se mantém em fixtures cruzando 1 MiB, 4 MiB e 64 MiB, com o teste afirmando o tamanho **antes** de rodar. | noturno |
| **AC-07** | Corpus A e B rodam no CI **sem workspace e sem JVM na camada de declaração**, em menos de um minuto. | interno |
| **AC-08a** | O check roda dentro do Spark contra **Delta local (OSS)** e reprova a task, sem credencial e sem workspace. `databricks/resources/*.yml` commitado. | noturno |
| **AC-08b** | **Uma** execução no workspace, agendada pelo Jorge, fora do loop, com o run id como evidência. | externo |
| **AC-09** | O diferencial compara contra `promote ∪ quarantine` de um `_batch_id`: registro roteado à quarentena **não** é reportado como dano. | interno |
| **AC-10** | `pip install ingestproof` funciona a partir do PyPI, com `py.typed` e attestations. | externo |
| **AC-11** | O PR de adoção insere o gate **no caminho de produção** do flagship, entre `promote` e `reclaim_landing`, e o CI de lá fica verde. | externo |
| **AC-12** | O ledger registra toda volta com o campo `author`, e o README publica a **divisão medida** entre humano e loop, mais **pelo menos um** caso do gate barrando o agente. | interno |
| **AC-13** | O README abre com a linha de base gratuita do DuckDB, com o script commitado e rodável. | — |
| **AC-14** | A tabela de prior art nomeia DQX, Lakebridge, DVT, Frictionless, Pollock, dlt e datacompy, cada um com o que deixa passar. | — |
| **AC-15** | Adicionar JSON Lines produz `git show --stat` com **0 arquivos modificados**. | noturno |
| **AC-16** | O loop abre o PR, espera o revisor concluir, e só marca achado como resolvido se o diff tocar o arquivo e as linhas citadas. Não mergeia. | interno |
| **AC-17** | Volta interrompida não contamina a seguinte: `reset --hard && clean -fdx` remove **arquivo não rastreado** plantado antes da volta. | interno |
| **AC-18** | O relatório é gravado numa tabela do **Unity Catalog** (`<catalog>.<schema>.<table>`), com owner e grant declarados no YAML do bundle. | noturno |
| **AC-19** | A VPS é reconstruída do zero pelo código commitado; `terraform plan` sai como comentário no PR e `apply` só roda no merge, de environment protegido. | externo |
| **AC-20** | O environment do Trusted Publisher é `pypi`, o environment homônimo no GitHub exige revisor, e existe **um run registrado que parou esperando aprovação**. | externo |

---

## 13. Fora de escopo

- Round-trip byte a byte e conservação escalar como checks. Mortos, e o porquê é conteúdo do README.
- Gate de wall-clock.
- Construir motor de rastreabilidade próprio — adotar OpenFastTrace.
- Formato além de CSV e JSON Lines.
- Qualquer trabalho no flagship que não seja o PR de adoção. As issues #25 e #26 já foram entregues àquela raia.

---

## 14. Riscos

| risco | mitigação |
|---|---|
| Proximidade do Databricks Labs DQX | A tabela de prior art nomeia DQX primeiro e diz o que ele não faz: comparar contra os **bytes de origem**. O diferencial é o delta, e ele é medido. |
| Escopo virar um segundo flagship | Camada 3 inteira é cortável; a P5 (VPS) e a P6 são opcionais. O inegociável é Camada 1 + Camada 2 + AC-11. |
| Enquadramento de autonomia derrubar a avaliação | **Liderar pelo gate, nunca pela autonomia.** Nunca "construído de madrugada", nunca contagem de commits, sem trailer `Co-Authored-By`. A seção "How this was built" publica a divisão **medida** (AC-12). |
| Competir por calendário com o flagship | Raias separadas, sem Databricks no loop, e a prova de adoção desacoplada do PR (§10). |
| O agente atacar o gate | Allowlist por hook fora do repositório + SHA-256 no CI + fechamento de tarefa definido externamente (§7.3, §7.6). |
| Falso verde por ambiente | Três resultados (§7.5) e manifesto do commit 1 (§7.12). |
| A parte nova não ser gateável | O diferencial e a resincronização são **escritos ou adjudicados** por humano; a divisão vai declarada por fase na §15 e medida no ledger. |

---

## 15. Fases

| fase | entrega | quem | gate |
|---|---|---|---|
| **P0 — Ambiente** | Repo, CI, manifesto do commit 1 (§7.12), `0.0.1` no PyPI, OFT + JRE 17, harness com ledger e allowlist, downloader do corpus (ASM-6), medições copiadas para `docs/` | **humano** (a allowlist proíbe o agente de autorar quatro destes) | AC-10, AC-16, AC-17; CI verde |
| **P1 — Contrato** | Declaração por tabela, guards de import, regras derivadas, quarentena e promoção — generalizados | mista | AC-01, AC-07 |
| **P2 — Fidelidade** | Dialeto declarado, diferencial, resincronização, relatório | **humano/adjudicado** no diferencial e na resincronização; loop no resto | AC-02a, AC-03, AC-04, AC-09 |
| **P3 — Plataforma** | Caminho Spark/Delta, tabela de auditoria em UC, YAML do bundle | mista | AC-08a, AC-18 |
| **P4 — Evidência** | Medição no corpus real, taxa de falso positivo, dry-run de adoção | mista | AC-02b, AC-05, AC-06 |
| **P5 — VPS** | Provisionamento por código, endurecimento, loop como serviço | mista | AC-19 |
| **P6 — Fechamento** | README com linha de base, prior art, resultados negativos e "How this was built"; PR de adoção; endurecimento do release | mista | AC-11, AC-12, AC-13, AC-14, AC-15, AC-20 |

**Cortáveis, nesta ordem:** P5, depois AC-15, depois o tokenizador de span. **Inegociáveis:** P1, P2 e AC-11.

**A prova no workspace (AC-08b)** é agendada pelo Jorge, fora de fase, quando a raia do flagship estiver parada.

---

## 16. Proveniência

Escrita depois de dois workflows multi-agente em 18/08/2026: `wf_ac565dc9-2df` (validação do desenho, 13 agentes — refutou 4 de 5 alegações) e `wf_e5f60444-dee` (revisão adversarial desta spec, 10 agentes — 9 bloqueadores, 32 altos, 4 de 4 alegações refutadas).

**Os journals são efêmeros por sessão. Todas as medições foram copiadas para `docs/superpowers/research/ingestproof-measurements.md`, que é a fonte durável.** Nenhum número deste documento pode ser citado sem estar lá — e a §12 daquele arquivo lista os que ainda não podem ser citados por procedência frágil.

Duas medições foram re-probadas pelo orquestrador em vez de aceitas por relatório, e **as duas mudaram o desenho**: o `reject_errors` do DuckDB só popula em linha rejeitada, e `reader.py` tem 67 linhas de código das quais 39 são encanamento do flagship.

A síntese e as decisões são do orquestrador; a fusão foi decidida pelo Jorge em 18/08.
