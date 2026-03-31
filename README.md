# Data Pipeline - Movies Dataset

Este projeto implementa um pipeline de engenharia de dados, processando um dataset de filmes desde a ingestão até a disponibilização em um Data Warehouse (PostgreSQL).

---

# 1. Arquitetura

## Fluxo de Dados

```text
Fonte (CSV - Kaggle)
        ↓
Python (RAW Layer)
        ↓
Parquet (SILVER Layer)
        ↓
PostgreSQL (GOLD Layer)
```

## Descrição
Fonte: Dataset CSV de filmes (Kaggle)
- RAW: Ingestão sem transformação
- SILVER: Limpeza, padronização e profiling
- GOLD: Modelagem dimensional (Star Schema) e carga no Postgres

# 2. Documentação da Tarefa
- Camada RAW

Responsabilidade:

Copiar dados brutos para o Data Lake
Organizar por partição de data (ano/mês/dia)

Saída:

data/raw/YYYY/MM/DD/dataset.csv
- Camada SILVER

Responsabilidade:

Limpeza de dados
Conversão de tipos
Tratamento de valores nulos
Remoção de duplicatas
Geração de profiling estatístico

Saída:

data/silver/YYYY/MM/DD/movies.parquet
data/silver/reports/ (relatórios)
- Camada GOLD

Responsabilidade:

Modelagem dimensional (Star Schema)
Carga incremental no Postgres
Uso de staging + COPY (alta performance)
UPSERT com ON CONFLICT

## Tabelas:

fact_movies
dim_language
dim_status

# 3. Dicionário de Dados
Coluna	Tipo	Descrição
id	int	Identificador único do filme
title	string	Nome do filme
vote_average	float	Média de avaliações
vote_count	int	Quantidade de votos
status	string	Status do filme (Released, etc.)
release_date	date	Data de lançamento
revenue	float	Receita total
runtime	int	Duração em minutos
adult	boolean	Indica conteúdo adulto
budget	float	Orçamento do filme
original_language	string	Idioma original
popularity	float	Score de popularidade
genres	string	Gêneros do filme
production_companies	string	Empresas produtoras

# 4. Qualidade de Dados

Durante o processamento na camada Silver, foram identificados os seguintes problemas:

- Valores nulos
overview: alta quantidade de valores vazios
homepage: grande volume de dados ausentes
release_date: registros inválidos ou nulos
- Dados inconsistentes
adult: valores mistos (string e boolean)
runtime: valores nulos e não numéricos
budget e revenue: valores faltantes tratados como 0
- Duplicidade
Registros duplicados com mesmo id
- Strings problemáticas
Campos com valores:
"nan"
"[]"
"None"

# 5. Instruções de Execução
- 1. Clonar o projeto
git clone <repo>
cd <repo>
- 2. Instalar dependências (modo local)
pip install -r requirements.txt
- 3. Executar com Docker
docker-compose up --build
- 4. Ordem de execução do pipeline

O worker executa automaticamente:

1. RawLayerProcessor
2. SilverLayerProcessor
3. GoldLayerProcessor
🔹 6. Acessar o banco Postgres
docker exec -it <container_db> psql -U postgres

Exemplo:

SELECT COUNT(*) FROM fact_movies;
SELECT * FROM dim_language LIMIT 10;
## Exemplos de Queries
- Top filmes por lucro
```
SELECT title, profit
FROM fact_movies
ORDER BY profit DESC
LIMIT 10;
```

- Receita por idioma
```
SELECT d.language_code, SUM(f.revenue)
FROM fact_movies f
JOIN dim_language d ON f.dim_language_id = d.id
GROUP BY d.language_code;
```