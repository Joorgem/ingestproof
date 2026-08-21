> Copied verbatim on 2026-08-20 from `docs/superpowers/research/ingestproof-measurements.md`
> in the private planning repository, which remains the origin. It travels with this
> repository because the design it supports once cited a session journal id that existed on
> no disk — a reviewer found that and classified it as a defect. Every number in this
> repository's README, pull requests and issues must be findable here.
>
> Numbers listed in §12 as fragile are **not citable** until they are re-derived. §12.6 is
> the exception, and the reason the rule works: it is not a fragile provenance, it is the
> re-derivation that **falsified** §9's DuckDB claim. Its numbers are citable, and the
> verbatim run behind them is `docs/duckdb-baseline-output.txt` in this repository.

# Medições — o que foi realmente executado, e o que cada número significa

**Data:** 2026-08-18
**Por que este arquivo existe:** a spec `2026-08-18-ingestproof-design.md` cita ~30 números
medidos e apontava, para todos eles, um id de journal de sessão (`wf_ac565dc9-2df`) que
**não existe em disco em nenhum dos dois repositórios**. Uma revisão adversarial encontrou
isso e classificou como HIGH: a próxima sessão seria mandada reproduzir e publicar artefatos
que não consegue abrir. Este arquivo é a fonte durável.

**Como foram produzidos:** dois workflows multi-agente rodados em 18/08/2026 —
`wf_ac565dc9-2df` (validação do desenho: 8 lentes + 5 refutadores) e `wf_e5f60444-dee`
(revisão adversarial da spec: 6 lentes + 4 refutadores). Os journals brutos vivem em
`~/.claude/projects/C--Users-jorge-.../subagents/workflows/<run-id>/journal.jsonl` e são
efêmeros por sessão. Os números abaixo foram extraídos deles e **os marcados com ✔ foram
re-probados diretamente pelo orquestrador**.

> **Regra de uso:** número sem procedência aqui é número que não pode ser citado em README,
> spec, PR ou entrevista. Se algo abaixo estiver marcado como não re-verificado, trate como
> alvo a reproduzir, não como evidência a citar.

---

## 1. A tese que sobreviveu — diferencial de dois parsers

Ferramenta: **univocity-parsers 2.9.1** (o parser que o leitor CSV do Spark embrulha),
configurado com as opções documentadas do flagship (`sep=';'`, `quote='"'`, `escape='"'`,
`unescapedQuoteHandling=STOP_AT_DELIMITER`, windows-1252), contra `csv.reader` do Python
(RFC 4180, `doublequote=True`, cp1252) como referência independente.

Corpus: CSV interno completo de `data/cnpj/2026-06/giants/Estabelecimentos6.zip` —
**4.753.435 registros**.

| medição | resultado |
|---|---|
| Divergências com o dialeto **correto** | **0** de 4.753.435 |
| Registros danificados detectados com o dialeto **quebrado** do Spark (`escape='\'`) | **459** |
| Desses, com contagem de campo intacta (30 campos) | **456** |
| Visíveis a checagem de aridade | **3** |
| Visíveis a contagem de linha, byte ou digest | **0** |

Histograma de contagem de campo no parse danificado: `{30: 4.753.433, 31: 1, 26: 1, 5: 1}`.

Exemplo concreto do dano — registro 13.730: `complemento` vira `": ""A""` e `bairro` vira
`";"DUCILIA CARONE"`, quando o correto é `: "A";` e `DUCILIA CARONE`.

**Por que isso mata os dois checks descartados:** 456 dos 459 danos preservam contagem de
campo, contagem de linha, total de bytes E digest do payload. Qualquer conservação escalar
passa reto. É o mesmo formato do incidente "a contagem fechou perfeitamente em volta do
dano" que o flagship já tinha sofrido.

### Taxa de falso positivo sob dialeto declarado errado

| cenário | falsos positivos | observação |
|---|---|---|
| CSV escrito pelo próprio Spark (`escape='\'`), lido com referência RFC 4180 | **452 de 459** | 448 deles com aridade limpa — indistinguíveis de dano real |
| Corpus da RFB com dialeto de backslash declarado por engano | **39** | todos de endereços com `S\N` ("sem número") |

> ⚠️ **Defeito de precisão herdado, a corrigir antes de publicar:** os dois cenários acima
> reusam o denominador **459**, que é o número de registros *danificados* de um experimento
> diferente. Uma taxa precisa de denominador próprio. Re-derivar antes de qualquer AC citá-la.

---

## 2. O que o leitor de referência NÃO entrega — e isto mudou o desenho

**✔ Re-probado pelo orquestrador. DuckDB 1.5.5, Python 3.12.**

```
read_csv('t.csv', store_rejects=true, strict_mode=true, columns={...})
linhas boas:  [('1', 'say "hi", bye'), ('2', 'ok')]
reject_errors cols: [scan_id, file_id, line, line_byte_position, byte_position,
                     column_idx, column_name, error_type, csv_line, error_message]
reject_errors:      [(3, 0, 4, 34, 37, 3, None, 'TOO MANY COLUMNS', '3,4,EXTRA', ...)]
```

**Conclusão:** o DuckDB emite posição de byte **somente para registros que ele rejeita**.
A linha do incidente — `1,"say ""hi"", bye"` — ele parseia **corretamente** e não emite
posição nenhuma.

Como a classe de dano inteira (os 456 acima) é, por definição, parseada **limpa** pelo lado
de referência, **atribuição de span sobre dado limpo não é obtenível do DuckDB.**

**Consequência de desenho:** DuckDB serve como **oráculo de VALOR**, não de posição.
Localização por byte exige tokenizador próprio (máquina de estado byte a byte emitindo
`(linha, campo, início, fim)` mais caracteres estruturais), ou o critério de aceite abandona
a promessa de posição de byte.

### Desempenho do DuckDB por encoding

| encoding | throughput single-core |
|---|---|
| utf-8 | ~121 MB/s |
| **cp1252** | **~15 MB/s** |

O caminho não-UTF-8 do DuckDB é single-threaded. Duas consequências: o piso de "~150 MB/s"
que a spec escreveu é **uma ordem de grandeza acima do real** para o corpus que importa; e a
comparação de `block_size`/`parallel` que escolheu DuckDB sobre PyArrow foi medida em UTF-8,
não em cp1252 — precisa ser refeita antes de a escolha de engine ser considerada firme.

Custo derivado: a parte 0 do Estabelecimentos tem CSV interno de **6.780.467.695 bytes /
29.093.533 linhas**, e sob `multiLine=true` não pode ser dividida entre tarefas (ADR 0005).
A 15 MB/s, só o parse de referência dela são **~7,4 minutos**, sem materializar campo nem
comparar — contra uma ingestão inteira medida em ~8m38s.

---

## 3. O problema de alinhamento registro↔linha

Medido: um arquivo de 1.000 registros com **um** registro contendo quebra de linha dentro de
campo citado faz o Spark emitir **1.001 linhas**. Um `zip` posicional entre referência e
tabela então reporta **~500 linhas divergentes para 1 dano real**.

O incidente do `escape` preserva a contagem de linha, então a medição da §1 nunca exercitou
esse caminho. **O alinhamento nunca foi projetado, e é onde ele quebra.**

Precisa de resincronização: após uma divergência, reancorar os dois fluxos (em K registros
byte-idênticos consecutivos, ou nos offsets estruturais de quebra de linha da referência) e
reportar um **span de dano limitado**, não uma diferença por linha.

---

## 4. O diferencial contra uma tabela Delta pousada gera falso positivo por construção

**Reproduzido com a topologia real do flagship:** Spark 3.5.9 local + delta-spark 3.3.1
(JDK 17), importando `csv_read_options()` do próprio `src/opl/bronze/reader.py`, sobre 1.000
registros no formato RFB com um registro de quebra de linha embutida e dez linhas falhando
legitimamente a regra `null_or_empty_municipio`.

```
bytes de origem: 289.748    registros de origem: 1.000
linhas em staging: 1.000
quarentena: 10  |  bronze Delta pousado: 990
referência (DuckDB, cp1252): 1.000
DANOS REPORTADOS PELO DIFERENCIAL: 10
dos quais realmente danificados na origem: 0
FALSOS POSITIVOS: 10  → 1,0% com ZERO dano de fidelidade
```

**Causa:** a tabela bronze não é a saída do parse. É a saída do parse **menos** os rejeitados
pelo gate de DQ, que vão para uma tabela de quarentena separada (`dq_gate_batch.py`,
`promote_batch.py`). O `multiLine` funcionou perfeitamente — os 1.000 registros ficaram
inteiros. O falso positivo é 100% atribuível ao gate fail-closed (ADR 0006).

**Alvo de comparação correto:** `promote ∪ quarantine` para um mesmo `_batch_id`, ou a tabela
de staging antes do gate. Nunca a bronze pousada.

### E não há chave de alinhamento do lado Delta

```
colunas do bronze Delta: [c0..c29, '_source_file']
_metadata disponível:    [file_block_length, file_block_start, file_modification_time,
                          file_name, file_path, file_size]
```

Esses campos de `_metadata` descrevem o **arquivo parquet do Delta**, não o CSV de origem.
A única proveniência de origem é a string `_source_file`. **Não há ordinal de registro, nem
offset de byte, nem índice de linha.**

Saída possível, e é a melhor: o PR de adoção acrescenta uma coluna de **ordinal de registro
de origem** ao bronze do flagship. É mudança pequena, defensável, no caminho de produção — e
um artefato bem mais forte que apagar um teste.

---

## 5. O modelo de execução do Nível 2 é proibido na plataforma alvo

Databricks Free Edition é serverless-only; todo job do flagship roda `environment_version: "3"`.
Serverless é Spark Connect. Da documentação da plataforma, e o flagship já mediu duas delas
por conta própria:

- *"Only Spark Connect APIs are supported. **Spark RDD APIs are not supported**"*
- *"User-defined custom code, such as UDFs, `map`, and `mapPartitions`, **cannot exceed 1 GB
  in memory usage**"*
- *"Dataframe and SQL cache APIs are not supported"* — medido no flagship:
  `docs/f2-wave-1-workspace-run-evidence.md:439` (`PERSIST TABLE is not supported on serverless`)
  e `docs/f3-workspace-run-evidence.md:422`.

E o flagship **não tem precedente nenhum** de execução Python por partição: um grep por
`mapPartitions|mapInPandas|mapInArrow|sparkContext|\.rdd|udf(|pandas_udf|foreachBatch|foreachPartition|binaryFile`
em `src/` e `databricks/src/` (27 arquivos) retorna **nada**. Ou seja, "o flagship já provou
que funciona" cobre trabalho DataFrame no driver, e só.

---

## 6. Os incidentes do corpus — o que reproduz sem Databricks

**Camada A — Python puro + stdlib**

| incidente | reprodução |
|---|---|
| `SystemExit` sob IPython | `pip install ipython` (9.16.1). `run_cell` sobre `raise SystemExit(main())` com `main()` retornando 0 → `success=False, error_in_exec=SystemExit(0)`, processo sai 0. **Não é comportamento do Databricks** — é `InteractiveShell.run_code` (ipython#8908). |
| Truncamento do `files.upload` do sdk 0.40 | Servidor de socket local (~60 linhas) que consome parte do corpo do PUT e envia RST. Payload 8.388.608 B. **0.40: retorna SUCESSO, grava 8.159.232 B — 229.376 perdidos em silêncio. 0.42.0: grava 8.388.608, zero perdido.** |
| `COUNT(DISTINCT a,b,c)` derrubando NULL | SQL padrão |

> **Correção factual necessária:** a causa do truncamento **não** é "não rebobinou antes do
> retry" em geral. A 0.40 **rebobina** em resposta de erro HTTP (um 429 retenta com o corpo
> completo, verificado). Ela falha só em **exceção de transporte**, porque o rebobinamento
> ficava depois da chamada ao parser de erro em `_perform`. O PR upstream #878 moveu para um
> hook `before_retry` — e **shipou sem teste de regressão**, o que é argumento a favor deste
> corpus existir.

**Camada B — Spark OSS via `pip install pyspark==4.2.0`** (Python 3.14, JDK 17, `local[1]`)

```
[A] multiLine=false → 3 linhas  [Row(id='1', note='line A'), Row(id='line B"', note=None), Row(id='2', note='ok')]
[A] multiLine=true  → 2 linhas  [Row(id='1', note='line A\nline B'), Row(id='2', note='ok')]
[B] escape ausente  → [Row(id='1', name='"say ""hi""')]        (delimitador engolido)
[B] escape='"'      → [Row(id='1', name='say "hi", bye')]
[C] schema explícito, PERMISSIVE → 2 linhas, campo extra descartado EM SILÊNCIO
[C] FAILFAST no mesmo arquivo    → MALFORMED_RECORD_IN_PARSING ... [4,5,6]
```

O contraste em `[C]` é o melhor parágrafo do corpus: **o parser sabia que o registro estava
danificado e descartou essa informação por padrão.**

**Camada C — precisa de workspace:** `_rescued_data` não popular (`cloudFiles` não existe no
Spark OSS — confirmado, delta-io/delta#1019), o retry de `INTERNAL_ERROR` do serviço de Jobs,
e a observação do log de deploy. Achado extra da sondagem: **o Spark OSS aceita
`rescuedDataColumn` e o ignora em silêncio** — a coluna nunca aparece, sem aviso. Isso é, em
si, uma falha de fidelidade digna de fixture.

---

## 7. Por que o loop não alcança este projeto sozinho

| medição | número |
|---|---|
| `hypothesis.internal.conjecture.engine.BUFFER_SIZE` | **8.192 bytes** |
| `st.binary(max_size=5_000_000)`, 300 exemplos, health checks suprimidos | maior exemplo gerado: **32 bytes**; exemplos ≥ 1 MiB: **0** |

O corpus deste projeto é medido em 67.960.832 bytes perdidos, 71,9M linhas, 11.631 linhas
danificadas. **O anel interno é rápido e determinístico precisamente porque nunca entra no
regime que a biblioteca existe para policiar.**

### O oráculo inverte o veredicto só pelo tamanho da entrada

PyArrow 25.0.1, formato do incidente §2.6 da RFC 4180, `use_threads=False`:

```
maior n OK:      48.167  (1.048.572 bytes)
primeiro n falho: 48.168  (1.048.594 bytes)   ← ReadOptions().block_size = 1.048.576
```

O **mesmo arquivo** de 1.048.594 bytes, mudando só o botão:

```
block_size=  262.144  → "CSV parser got out of sync with chunker"
block_size=1.048.576  → "Row #48170: Expected 2 columns, got 1"  ← RE-SEGMENTA em silêncio
block_size=4.194.304  → OK, 48.168 linhas
```

`newlines_in_values=True` corrige, a um custo medido de **4,5x** (0,050s vs 0,011s). DuckDB
1.5.5 acertou em todos os tamanhos, com `parallel` ligado e desligado — **mas em UTF-8**
(ver §2).

### As fixtures byte-exatas não são byte-estáveis

Um commit, `id,note\n1,"line A\nline B"\n2,ok\n`, três clones:

```
autocrlf=true   → b'id,note\r\n1,"line A\r\nline B"\r\n2,ok\r\n'
autocrlf=input  → LF preservado
autocrlf=false  → LF preservado
* text=auto + autocrlf=true → CRLF de novo
```

O git reescreve **inclusive a quebra de linha dentro do campo citado** — ou seja, edita em
silêncio a fixture de regressão da RFC 4180 §2.6. Numa biblioteca cuja tese é fidelidade de
byte, isso é fatal, e o loop não teria como descobrir sozinho. Corrige com `-text` em toda
extensão de fixture, no commit 1.

### E o `reset` não limpa o que mais importa

`git reset --hard` **não remove arquivo não rastreado**. Um `conftest.py` órfão na raiz, um
`test_*.py` solto ou um `.hypothesis/` deixados por uma volta morta sobrevivem para a
seguinte — e foi verificado que isso **transforma uma suíte de aceite vermelha em verde**.
A regra precisa ser `reset --hard && clean -fdx` (com exclusões), ou worktree descartável.

---

## 8. Ferramental — o que não é o que parece

| alegação | realidade medida |
|---|---|
| OpenFastTrace instalável por pip | **Falso.** `openfasttrace`, `open-fasttrace`, `oft-core` → todos 404 no PyPI. É JAR de **Java 17** (release 4.9.0, `openfasttrace-4.9.0.jar` + `.sha256`). A máquina tem **Java 11**. |
| OFT pega requisito sem cobertura por padrão | **Parcial.** Item sem campo `Needs:` é *terminating item* e traça limpo. `Needs:` tem que ser obrigatório, com check de CI. |
| OFT pega deriva de revisão sozinho | **Falso.** Depende de alguém **incrementar a revisão manualmente**. O equivalente mecânico é o CI guardar SHA-256 do texto de cada critério. |
| Gramática de id do OFT | `req~nome~revisão` — **não** casa com `AC-01`..`AC-17` da spec. |
| mutmut como gate | mutmut 3 só muta **dentro de funções** — constante em nível de módulo produz zero mutantes. E precisa de `fork`, indisponível no Windows: o anel de mutação roda **só em Linux** (CI ou VPS). |
| Benchmark de wall-clock como gate | Teatro em runner compartilhado: a variância engole qualquer limiar. |

---

## 9. Prior art — o que já existe

- **Pollock** (VLDB 2023, Vitagliano et al., HPI, MIT) — benchmark formal de perda silenciosa
  arquivo→tabela, com precisão/recall/F1 em nível de cabeçalho, registro e célula. DuckDB
  publicou sobre ele em 2025 e lidera com **9,961**.
- **Reconciliação source-to-target** é categoria nomeada com ~12 implementações: Soda recon,
  **Databricks Lakebridge**, **Databricks Labs DQX `compare_datasets`** (447 estrelas),
  Bigeye Deltas, Monte Carlo, Anomalo, Datafold `data-diff` (arquivado), Google DVT,
  dbt `audit_helper`, Deequ `DataSynchronization`, `datacompy`, QuerySurge/iceDQ/Datagaps.
- **Google DVT** aceita arquivo (conexão `FileSystem`) mas lê com `pandas.read_csv(file_path)`
  puro, sem dialeto declarado, e sua própria documentação exclui validação por hash de linha
  para conexões de arquivo. É o vizinho mais próximo e o que melhor demonstra a lacuna.
- **Frictionless** já entrega conservação de fábrica (`HashCountError`, `ByteCountError`,
  `FieldCountError`, `RowCountError`).
- ~~Um script de **12 linhas de DuckDB** detecta os três incidentes de CSV com controle negativo
  limpo.~~ **Falsificado em 19/08/2026 — ver §12.6.** O script existe, é medido, e **precisa
  abrir o README** — mas detecta **um** dos três incidentes, não os três.

---

## 10. Sobre a proveniência do próprio artefato

**✔ Re-probado.** `src/opl/bronze/reader.py`: 278 linhas brutas = 85 comentário + 42 branco +
151 outras; despido de comentários e docstrings, **67 linhas de código**. Dessas, **39 são
despacho sobre o catálogo de contratos do flagship** — sem sentido fora de
`open-payments-lakehouse`. O que sobra são dois dicionários de opção do Spark, que na
biblioteca nova são **entrada a ser auditada**, não código.

`git log --follow` no arquivo: 9 commits na vida dele. Os dois incidentes de CSV foram
fechados por `2673031` (`+16`, cujo código é `"multiLine": "true"`) e `536f762` (`+33/-3`,
cujo código é `"escape": CSV_DIALECT["quotechar"]`). **Duas entradas de dicionário.**

Grep sobre 27.106 linhas de Python em `src/` e `tests/`: `duckdb` 0 arquivos, `byte_offset` 0,
`differential` 0, `import csv` **zero vezes em `src/`**.

**Conclusão: "módulo extraído" não sobrevive ao `git log --stat`.** O que atravessa é o
literal `CSV_DIALECT` (`src/opl/contracts/cnpj_schemas.py:7-14`, 6 chaves das quais 4 usadas),
os dois dicionários de opção como fixture, seis registros verbatim, e as narrativas medidas.
O termo honesto é **"deriva de"**.

E o protótipo real que a spec **omitia**: `tests/bronze/test_reader_multiline.py::test_real_doubled_quote_records_match_rfc4180_field_for_field`
— o flagship já rodou o diferencial contra `csv.reader` à mão, e foi assim que o incidente do
`escape` foi encontrado. É a prior art de verdade, e ela é de casa.

---

## 11. Estado da raia vizinha (para sequenciamento)

Medido em 18/08: o flagship está com a **F4 em voo** (branch `feat/f4-dataops`, Task 5 de 8) e
a **F5 (Streaming) não começou**, com o plano deliberadamente não escrito. Na cadência recente
(F3 ~4 dias, F-API ~2, F-DB ~3), o PR de adoção depender de F4+F5 põe ele a **10–20 dias**.

E a justificativa da espera é empiricamente falsa: **a F4 não toca nem `src/opl/bronze/reader.py`
nem `tests/bronze/test_reader_multiline.py`**. Não há colisão a evitar.

Prova mais barata, disponível no dia em que a F1 fechar: rodar contra os arquivos e tabelas
que o flagship **já pousou**, e publicar o resultado — achou ou não achou — como
`docs/adoption-dry-run.md` no repo novo.

---

## 12. Números com procedência frágil — não citar sem re-derivar

1. **A taxa de falso positivo** (§1) reusa o denominador 459 de outro experimento.
2. **4.753.435 vs 4.753.436** — a spec diz 435; `src/opl/bronze/reader.py:65` diz "461 of
   4,753,436". Um é contagem de registro, o outro provavelmente de LF. Precisa ser reconciliado.
3. **Dois `Estabelecimentos6.zip` diferentes existem** localmente: 2026-06 (366.882.667 B) e
   2026-07 (368.109.911 B), ambos em `data/` que é git-ignored (`git ls-files data` = 0, 14 GB).
   Nenhum critério de aceite pode citar "o Estabelecimentos6" sem fixar mês e SHA-256.
4. **Os limites semânticos da §3 da spec** (vazio-vs-nulo, cp1252 nas bordas) foram derivados
   com **Python** como referência, mas o desenho escolheu **DuckDB**. O DuckDB tem um terceiro
   comportamento nos dois. Precisa ser re-derivado contra o engine que vai ser usado.
5. **Quarto limite não registrado:** os dois parsers discordam sobre CR isolado dentro de
   campo citado — dado ou terminador de registro — e o leitor de produção **reescreve o byte**.
   É um canal de re-segmentação dentro da tese que sobreviveu.
6. **A alegação da §9 — "12 linhas de DuckDB detectam os três incidentes" — é FALSA.**
   Medido em **19/08/2026**, DuckDB **1.5.5**, Python 3.12, script real em
   `tools/duckdb_baseline.py` do `ingestproof` (saída verbatim em
   `docs/duckdb-baseline-output.txt`):

   ```
   duckdb 1.5.5
   multiline.csv:    2 rows accepted, 0 rejected
   escape.csv:       1 rows accepted, 0 rejected
   extra_field.csv:  2 rows accepted, 1 rejected
       line=4 col=3 TOO MANY COLUMNS: '3,4,EXTRA'
   clean.csv:        3 rows accepted, 0 rejected
   ```

   Detecta **1 de 3**: só o `extra_field`. Os outros dois ele parseia **corretamente e em
   silêncio** — `('1', 'line A
line B'), ('2', 'ok')` e `('1', 'say "hi", bye')` — que é a
   §2 chegando à sua conclusão inevitável: os incidentes são dano do **leitor de produção**,
   não do arquivo, e um parser correto não tem o que rejeitar. Só o `extra_field` é malformado
   contra o schema declarado, e é por isso que é o único que aparece.

   Consequência para o README: a linha de abertura não é "o grátis já resolve, nós localizamos".
   É **"o grátis acha 1 de 3, e os 2 que ele deixa passar são exatamente a classe que exige
   dois parsers em vez de um"** — número medido, não asserção. Uma abertura melhor que a versão
   forte, e a única que sobrevive a alguém rodar o script.

   ~~Duas armadilhas de implementação encontradas no caminho, ambas silenciosas: o
   `SELECT count(*) FROM read_csv(...)` otimizado para dentro do scan, e o `fetchone()`
   deixando o resultado aberto.~~ **É UMA, não duas — corrigido em 20/08/2026.** A matriz 2x2
   completa, medida com conexão nova por célula e reproduzida por três partes independentes:

   ```
   duckdb 1.5.5, clean.csv e extra_field.csv
   fetchall  -> tabela de rejeitos PRESENTE nas 4 células, inclusive no count(*) PELADO
   fetchone  -> CatalogException nas 4 células
   ```

   **Drenar o resultado é a causa; o subquery é inerte.** A primeira armadilha não existe. O
   `EXPLAIN` fecha: o único efeito do wrapper era uma projeção constante sobre o mesmo nó
   `READ_CSV`. Ele foi removido do `tools/duckdb_baseline.py` em `a01115d`, com a saída do
   `main()` byte-idêntica — o blob de `docs/duckdb-baseline-output.txt` é o mesmo nos seis
   commits da tarefa.

   Cuidado com a leitura de suficiência: drenar é **necessário e não suficiente**. Com
   `store_rejects=false`, o `fetchall` também levanta `CatalogException`.

   Uma segunda alegação da mesma varredura caiu junto: o `columns` **é** parâmetro vinculável
   no duckdb 1.5.5 — o mesmo mapeamento passado como `?` devolve os mesmos nomes, os mesmos
   tipos declarados (`INTEGER` honrado, não default), as mesmas linhas e os mesmos rejeitos que
   o literal STRUCT. A cláusula continua textual, agora por escolha declarada e não por
   impossibilidade alegada.

   A contagem de linhas da §9 também não se sustenta — e **vem ancorada a um commit, porque
   sem âncora ela envelhece**: entre a primeira medição e a última, o mesmo arquivo passou por
   49, 54, 55, 59 e 64. Em **`716b7b4`**, medido por dois métodos independentes que concordam
   (só o docstring de módulo, e todos os docstrings via AST):

   | medida | valor |
   |---|---|
   | linhas brutas | 111 |
   | brancas | 19 |
   | de comentário | 28 |
   | **não-comentário e não-branco** | **64** |
   | docstring de módulo (não há docstring de função) | 28 |
   | **núcleo executável** | **36** |

   O número vem com o método ao lado de propósito: um número sem método é exatamente o defeito
   que a §9 é. Publicar "64 contra 12" sem dizer que 28 são docstring seria repetir o gênero
   uma camada abaixo. O que derruba o "12" é a ordem de grandeza — 36 linhas de código
   executável, três vezes o alegado —, não o dígito.

7. **"Medido em 4 de 8 eixos"** (§3.2 do desenho) **não tem derivação neste documento.**
   Achado em 20/08/2026 pelo implementador da Tarefa 12, ao rodar o próprio gate que o README
   carrega: o README afirma que todo número dele está aqui, e este não estava. Escapou ao gate
   por um motivo que vale registrar — a regex exige três caracteres, então `4` e `8` sozinhos
   são **invisíveis** para ela. O gate cobre números longos, não números pequenos.
   Saiu do README. Não é citável em lugar nenhum até que os oito eixos sejam nomeados e os
   quatro que falsopositivam sejam re-medidos.
