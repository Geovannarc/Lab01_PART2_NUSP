import pandas as pd
from sqlalchemy import create_engine, text
from pathlib import Path
import os
import tempfile


class GoldLayerProcessor:
    def __init__(self):
        DB_NAME = os.getenv("POSTGRES_DB", "postgres")
        DB_USER = os.getenv("POSTGRES_USER", "postgres")
        DB_PASS = os.getenv("POSTGRES_PASSWORD", "postgres")
        DB_HOST = os.getenv("DB_HOST", "db")
        DB_PORT = os.getenv("DB_PORT", "5432")
        DB_URL = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

        self.engine = create_engine(DB_URL)
        base = Path(os.getenv("RAW_OUTPUT_PATH", "/app"))
        self.silver_path = base / "data" / "silver"

    def _get_latest_silver(self):
        partitions = sorted(self.silver_path.glob("*/*/*"))
        return partitions[-1] / "movies.parquet"

    def run(self):
        df = pd.read_parquet(self._get_latest_silver())

        df = self._prepare(df)

        self._copy_to_staging(df)
        self._merge_dimensions()
        self._merge_fact()

    def _prepare(self, df):

        df["profit"] = df["revenue"] - df["budget"]

        return df[[
            "id", "title", "release_date",
            "revenue", "budget", "profit",
            "vote_average", "vote_count", "popularity",
            "original_language", "status"
        ]].rename(columns={"id": "movie_id"})

    def _copy_to_staging(self, df):

        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".csv") as tmp:

            df.to_csv(tmp.name, index=False, header=False)

            conn = self.engine.raw_connection()
            try:
                cur = conn.cursor()
                with open(tmp.name, "r") as f:
                    cur.copy_expert("""
                        COPY staging_movies (
                            movie_id, title, release_date,
                            revenue, budget, profit,
                            vote_average, vote_count, popularity,
                            original_language, status
                        )
                        FROM STDIN WITH CSV
                    """, f)
                conn.commit()
            finally:
                cur.close()
                conn.close()

    def _merge_dimensions(self):

        with self.engine.begin() as conn:

            conn.execute(text("""
                INSERT INTO dim_language (language_code)
                SELECT DISTINCT original_language
                FROM staging_movies
                WHERE original_language IS NOT NULL
                ON CONFLICT (language_code) DO NOTHING
            """))

            conn.execute(text("""
                INSERT INTO dim_status (status)
                SELECT DISTINCT status
                FROM staging_movies
                WHERE status IS NOT NULL
                ON CONFLICT (status) DO NOTHING
            """))

    def _merge_fact(self):

        with self.engine.begin() as conn:

            conn.execute(text("""
                INSERT INTO fact_movies (
                    movie_id, title, release_date,
                    revenue, budget, profit,
                    vote_average, vote_count, popularity,
                    dim_language_id, dim_status_id
                )
                SELECT
                    s.movie_id,
                    s.title,
                    s.release_date,
                    s.revenue,
                    s.budget,
                    s.profit,
                    s.vote_average,
                    s.vote_count,
                    s.popularity,
                    dl.id,
                    ds.id
                FROM staging_movies s
                LEFT JOIN dim_language dl
                    ON s.original_language = dl.language_code
                LEFT JOIN dim_status ds
                    ON s.status = ds.status

                ON CONFLICT (movie_id)
                DO UPDATE SET
                    title = EXCLUDED.title,
                    release_date = EXCLUDED.release_date,
                    revenue = EXCLUDED.revenue,
                    budget = EXCLUDED.budget,
                    profit = EXCLUDED.profit,
                    vote_average = EXCLUDED.vote_average,
                    vote_count = EXCLUDED.vote_count,
                    popularity = EXCLUDED.popularity,
                    dim_language_id = EXCLUDED.dim_language_id,
                    dim_status_id = EXCLUDED.dim_status_id,
                    updated_at = CURRENT_TIMESTAMP
            """))
            conn.execute(text("TRUNCATE staging_movies"))