# Data Pipeline - Movies Dataset

Este projeto implementa um pipeline de engenharia de dados, processando um dataset de filmes desde a ingestão até a disponibilização em um Data Warehouse (PostgreSQL), com validação de qualidade via Great Expectations e visualização via Grafana.

---

## 1. Arquitetura

```text
Fonte (CSV - Kaggle)
        ↓
Python (RAW Layer)     ← validação Great Expectations
        ↓
Parquet (SILVER Layer)
        ↓
PostgreSQL (GOLD Layer)
        ↓
Grafana (Dashboards) + Data Docs (Great Expectations)
```

### Descrição das Camadas

| Camada | Responsabilidade | Saída |
|---|---|---|
| **RAW** | Ingestão sem transformação, organização por partição de data | `data/raw/YYYY/MM/DD/dataset.csv` |
| **SILVER** | Limpeza, padronização, remoção de duplicatas, profiling | `data/silver/YYYY/MM/DD/movies.parquet` |
| **GOLD** | Modelagem dimensional (Star Schema), carga incremental no Postgres | Tabelas `fact_movies`, `dim_language`, `dim_status` |

---

## 2. Pré-requisitos

- [Docker](https://www.docker.com/) e Docker Compose instalados
- Dataset `dataset.csv` disponível no caminho configurado em `RAW_INPUT_PATH`

---

## 3. Subindo os Containers

### Primeira execução

```bash
docker-compose up --build
```

### Execuções subsequentes (sem rebuild)

```bash
docker-compose up
```

### Parar todos os containers

```bash
docker-compose down
```

### Recriar do zero (apaga volumes)

```bash
docker-compose down -v
docker-compose up --build
```

### Ordem de inicialização

1. `db` — PostgreSQL sobe primeiro
2. `worker` — aguarda o banco ficar pronto, executa o pipeline completo (RAW → SILVER → GOLD) e encerra
3. `datadocs` — nginx que serve os Data Docs do Great Expectations
4. `grafana` — dashboard conectado ao PostgreSQL

---

## 4. Serviços e Portas

| Serviço | URL | Credenciais |
|---|---|---|
| **Grafana** | http://localhost:3001 | admin / admin1 |
| **Data Docs (GX)** | http://localhost:8080 | — |
| **PostgreSQL** | localhost:5432 | postgres / postgres |

---

## 5. Visualizando o Resultado do Great Expectations (Data Docs)

O Great Expectations gera um relatório HTML estático com os resultados de todas as validações após cada execução do pipeline.

### Passo a passo

1. Execute o pipeline completo:
   ```bash
   docker-compose up --build
   ```

2. Aguarde o worker finalizar. Você verá no log:
   ```
   ✓ Data Docs built at /app/gx/uncommitted/data_docs/local_site/
   ```

3. Acesse no navegador:
   ```
   http://localhost:8080
   ```

4. A página inicial exibe o **índice de validações**. Clique em qualquer entrada para ver o resultado detalhado de cada expectativa.

### O que você encontrará no relatório

- **Overview** — resumo de quantas expectativas passaram e falharam
- **Expectations** — lista completa com resultado individual de cada regra:
  - `id`: não nulo, único, existe
  - `title`: não nulo, existe
  - `release_date`: intervalo válido (1888–2030)
  - `vote_average`: entre 0 e 10
  - `vote_count`, `revenue`, `budget`: valores não negativos
  - `original_language`: formato de 2 letras minúsculas
  - `status`: valores dentro do conjunto esperado
  - `genres`, `production_companies`, `production_countries`: tipo string

> **Nota:** os Data Docs são atualizados a cada execução do worker. Para ver novos resultados, execute `docker-compose up` novamente.

---

## 6. Visualizando os Gráficos no Grafana

### Passo a passo

1. Certifique-se de que os containers estão rodando:
   ```bash
   docker-compose up
   ```

2. Acesse o Grafana no navegador:
   ```
   http://localhost:3001
   ```

3. Faça login com as credenciais:
   - **Usuário:** `admin`
   - **Senha:** `admin1`

4. O dashboard **"Movies Analytics"** abre automaticamente como página inicial.

   Caso não abra, navegue por: **Dashboards → Movies Analytics**

### Painéis disponíveis

| Painel | Pergunta de negócio |
|---|---|
| **Total de Filmes** | Quantos filmes estão no dataset? |
| **Receita Total** | Qual foi a receita total acumulada? |
| **Média de Avaliação** | Qual a nota média geral dos filmes? |
| **Total de Idiomas** | Quantos idiomas originais existem? |
| **Top 10 Filmes por Lucro** | Quais filmes geraram maior lucro (receita − orçamento)? |
| **Receita Total por Idioma** | Qual idioma original acumulou mais receita? |
| **Distribuição por Status** | Como os filmes se distribuem por status de produção? |
| **Média de Avaliação por Idioma** | Qual idioma tem filmes mais bem avaliados? |
| **Filmes por Ano de Lançamento** | Como a produção de filmes evoluiu ao longo dos anos? |
| **Top 10 por Popularidade** | Quais filmes têm maior score de popularidade? |

### Primeira execução — datasource

O datasource PostgreSQL é provisionado automaticamente. Se aparecer a mensagem **"No data"** em algum painel:

1. Verifique se o worker já finalizou (a carga no Postgres só ocorre na camada GOLD)
2. Acesse **Connections → Data Sources → PostgreSQL** e clique em **"Save & Test"** para confirmar a conexão

---

## 7. Dicionário de Dados

| Coluna | Tipo | Descrição |
|---|---|---|
| `id` | int | Identificador único do filme |
| `title` | string | Nome do filme |
| `vote_average` | float | Média de avaliações (0–10) |
| `vote_count` | int | Quantidade de votos |
| `status` | string | Status do filme (Released, etc.) |
| `release_date` | date | Data de lançamento |
| `revenue` | numeric | Receita total |
| `runtime` | int | Duração em minutos |
| `adult` | boolean | Indica conteúdo adulto |
| `budget` | numeric | Orçamento do filme |
| `original_language` | string | Idioma original (código ISO 639-1) |
| `popularity` | float | Score de popularidade |
| `genres` | string | Gêneros do filme |
| `production_companies` | string | Empresas produtoras |

---

## 8. Modelagem — Star Schema (Camada GOLD)

```
        dim_language          dim_status
        (id, language_code)   (id, status)
              │                     │
              └──────┬──────────────┘
                 fact_movies
          (movie_id, title, release_date,
           revenue, budget, profit,
           vote_average, vote_count, popularity,
           dim_language_id, dim_status_id)
```

---

## 9. Qualidade de Dados

Problemas identificados durante o processamento na camada SILVER:

| Problema | Campos afetados |
|---|---|
| Valores nulos | `overview`, `homepage`, `release_date` |
| Tipos inconsistentes | `adult` (string e boolean misturados) |
| Valores não numéricos | `runtime`, `budget`, `revenue` |
| Duplicatas | Registros com mesmo `id` |
| Strings inválidas | Campos com `"nan"`, `"[]"`, `"None"` |

---

## 10. Exemplos de Queries

**Top filmes por lucro**
```sql
SELECT title, profit
FROM fact_movies
ORDER BY profit DESC
LIMIT 10;
```

**Receita por idioma**
```sql
SELECT d.language_code, SUM(f.revenue) AS receita_total
FROM fact_movies f
JOIN dim_language d ON f.dim_language_id = d.id
GROUP BY d.language_code
ORDER BY receita_total DESC;
```

**Distribuição por status**
```sql
SELECT ds.status, COUNT(*) AS total
FROM fact_movies f
JOIN dim_status ds ON f.dim_status_id = ds.id
GROUP BY ds.status
ORDER BY total DESC;
```

**Média de avaliação por idioma (mín. 50 filmes)**
```sql
SELECT d.language_code, ROUND(AVG(f.vote_average)::numeric, 2) AS media
FROM fact_movies f
JOIN dim_language d ON f.dim_language_id = d.id
WHERE f.vote_average > 0
GROUP BY d.language_code
HAVING COUNT(*) >= 50
ORDER BY media DESC;
```

**Filmes lançados por ano**
```sql
SELECT EXTRACT(YEAR FROM release_date)::int AS ano, COUNT(*) AS total
FROM fact_movies
WHERE release_date IS NOT NULL
GROUP BY ano
ORDER BY ano;
```
