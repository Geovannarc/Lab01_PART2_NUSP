from pathlib import Path
from datetime import datetime
import pandas as pd
import os
from log_utils import get_logger

class SilverLayerProcessor:
    def __init__(self):
        self.logger = get_logger(self.__class__.__name__)

    def run(self):
        self.logger.info("Iniciando processamento da camada silver")

        base_path = Path(os.getenv("RAW_OUTPUT_PATH", "/app"))

        raw_path = base_path / "data" / "raw"
        silver_base = base_path / "data" / "silver"

        latest_partition = self._get_latest_partition(raw_path)

        self.logger.info(f"Usando partição raw: {latest_partition}")

        df = self._read_raw(latest_partition)

        df = self._clean(df)
        df = self._transform(df)
        self._profile(df)

        output_path = self._write(df, silver_base)

        self.logger.info(f"Silver finalizado. Output: {output_path}")
        return str(output_path)

    def _read_raw(self, partition_path: Path) -> pd.DataFrame:
        files = list(partition_path.glob("*.csv"))

        if not files:
            raise FileNotFoundError(f"Nenhum CSV encontrado em {partition_path}")

        df = pd.concat([pd.read_csv(f) for f in files], ignore_index=True)
        return df

    def _clean(self, df: pd.DataFrame) -> pd.DataFrame:
        self.logger.info("Executando limpeza de dados")

        df = df.drop_duplicates(subset=["id"])

        df = df.replace({"": None})

        return df

    def _transform(self, df: pd.DataFrame) -> pd.DataFrame:
        self.logger.info("Executando transformações")

        df["release_date"] = pd.to_datetime(df["release_date"], errors="coerce")

        numeric_cols = [
            "vote_average",
            "vote_count",
            "revenue",
            "runtime",
            "budget",
            "popularity",
        ]

        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        df["adult"] = df["adult"].astype("boolean")

        return df

    def _profile(self, df: pd.DataFrame):
        self.logger.info("Gerando profiling estatístico avançado")

        report_path = Path(os.getenv("RAW_OUTPUT_PATH", "/app")) / "data" / "silver" / "reports"
        report_path.mkdir(parents=True, exist_ok=True)

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        total_rows = len(df)
        nulls = df.isnull().sum()
        null_pct = (nulls / total_rows * 100).round(2)

        dq_table = pd.DataFrame({
            "null_count": nulls,
            "null_pct": null_pct
        }).sort_values(by="null_pct", ascending=False)

        numeric_df = df.select_dtypes(include="number")
        numeric_stats = numeric_df.describe().T

        numeric_stats["median"] = numeric_df.median()
        numeric_stats["skew"] = numeric_df.skew()

        cat_df = df.select_dtypes(include=["object", "string"])

        top_categories = {}

        exclude_cols = {
            "title",
            "original_title",
            "overview",
            "tagline",
            "homepage",
            "imdb_id",
            "poster_path",
            "backdrop_path"
        }

        for col in cat_df.columns:

            if col in exclude_cols:
                continue

            series = df[col].dropna()

            if series.empty:
                continue

            cardinality_ratio = series.nunique() / len(df)
            if cardinality_ratio > 0.05:
                continue

            avg_len = series.astype(str).str.len().mean()
            if avg_len > 50:
                continue

            top_categories[col] = series.value_counts().head(5)

        insights = {}

        if "revenue" in df.columns:
            insights["top_10_revenue"] = df.nlargest(10, "revenue")[["title", "revenue"]]

        if "vote_average" in df.columns:
            insights["top_rated"] = df.nlargest(10, "vote_average")[["title", "vote_average"]]

        if "original_language" in df.columns:
            insights["language_distribution"] = df["original_language"].value_counts().head(10)

        content = f"# Relatório Silver\n\n"
        content += f"Data: {now}\n\n"

        content += "## 📊 Data Quality\n"
        content += dq_table.to_markdown() + "\n\n"

        content += "## 📈 Estatísticas Numéricas\n"
        content += numeric_stats.to_markdown() + "\n\n"

        content += "## 🔤 Top Categorias\n"
        for col, values in top_categories.items():
            content += f"### {col}\n"
            content += values.to_markdown() + "\n\n"

        content += "## 💰 Insights de Negócio\n"

        if "top_10_revenue" in insights:
            content += "### Top 10 por Receita\n"
            content += insights["top_10_revenue"].to_markdown(index=False) + "\n\n"

        if "top_rated" in insights:
            content += "### Top Avaliados\n"
            content += insights["top_rated"].to_markdown(index=False) + "\n\n"

        if "language_distribution" in insights:
            content += "### Distribuição por Idioma\n"
            content += insights["language_distribution"].to_markdown() + "\n\n"

        report_file = report_path / "silver_report.md"

        with open(report_file, "w", encoding="utf-8") as f:
            f.write(content)

        self.logger.info(f"Relatório salvo em: {report_file}")

    def _write(self, df: pd.DataFrame, base: Path) -> Path:
        now = datetime.now()

        path = (
            base
            / f"{now.year}"
            / f"{now.month:02d}"
            / f"{now.day:02d}"
        )

        path.mkdir(parents=True, exist_ok=True)

        output_file = path / "movies.parquet"
        df.to_parquet(output_file, index=False)

        return output_file

    def _get_latest_partition(self, raw_base: Path) -> Path:
        partitions = sorted(raw_base.glob("*/*/*"))

        if not partitions:
            raise FileNotFoundError("Nenhuma partição raw encontrada")

        return partitions[-1]