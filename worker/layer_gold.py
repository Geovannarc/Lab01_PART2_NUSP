import pandas as pd
from sqlalchemy import create_engine, text
from pathlib import Path
import os
import json


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
        self._merge_dimensions(df)
        print("✓ Gold layer processing completed successfully!")

    def _prepare(self, df):
        df["profit"] = df["revenue"] - df["budget"]
        return df[[
            "id", "title", "release_date",
            "revenue", "budget", "profit",
            "vote_average", "vote_count", "popularity",
            "original_language", "status",
            "genres", "production_companies", "production_countries"
        ]].rename(columns={"id": "movie_id"})

    def _parse_list_field(self, value):
        """
        Normaliza um campo que pode estar em diferentes formatos:
        - lista Python
        - dict (ignorado aqui)
        - string JSON
        - string CSV: "A, B, C"
        Retorna sempre uma lista de strings limpas.
        """
        if pd.isna(value):
            return []

        if isinstance(value, list):
            result = []
            for v in value:
                if isinstance(v, str):
                    v = v.strip()
                    if v:
                        result.append(v)
                elif isinstance(v, dict) and "name" in v and isinstance(v["name"], str):
                    name = v["name"].strip()
                    if name:
                        result.append(name)
            return result

        if isinstance(value, dict):
            if "name" in value and isinstance(value["name"], str):
                name = value["name"].strip()
                return [name] if name else []
            return []

        if not isinstance(value, str):
            return []

        value = value.strip()
        if not value:
            return []

        parsed = None
        try:
            parsed = json.loads(value.replace("'", '"'))
        except Exception:
            parsed = None

        if isinstance(parsed, list):
            result = []
            for v in parsed:
                if isinstance(v, str):
                    v = v.strip()
                    if v:
                        result.append(v)
                elif isinstance(v, dict) and "name" in v and isinstance(v["name"], str):
                    name = v["name"].strip()
                    if name:
                        result.append(name)
            if result:
                return result

        if isinstance(parsed, dict):
            if "name" in parsed and isinstance(parsed["name"], str):
                name = parsed["name"].strip()
                return [name] if name else []

        parts = [p.strip() for p in value.split(",") if p.strip()]
        return parts

    def _merge_dimensions(self, df):
        with self.engine.begin() as conn:
            print("Inserting dim_language...")
            self._insert_languages(df, conn)
            
            print("Inserting dim_genre...")
            self._insert_genres(df, conn)
            
            print("Inserting dim_production_company...")
            self._insert_companies(df, conn)
            
            print("Inserting dim_production_country...")
            self._insert_countries(df, conn)
            
            print("Inserting dim_movies...")
            movies_df = self._insert_movies(df, conn)
            inserted_movie_ids = set(movies_df["movie_id"].astype(int).unique())
            
            df_filtered = df[df["movie_id"].astype(int).isin(inserted_movie_ids)].copy()

            print("Populating bridge_movie_genre...")
            self._populate_bridge_movie_genre(df_filtered, conn)

            print("Populating bridge_movie_language...")
            self._populate_bridge_movie_language(df_filtered, conn)

            print("Populating bridge_movie_production_company...")
            self._populate_bridge_movie_production_company(df_filtered, conn)

            print("Populating bridge_movie_production_country...")
            self._populate_bridge_movie_production_country(df_filtered, conn)

    def _insert_languages(self, df, conn):
        languages = df["original_language"].dropna().unique().tolist()
        if languages:
            conn.execute(
                text("""
                    INSERT INTO dim_language (language_code)
                    SELECT UNNEST(:languages)
                    ON CONFLICT (language_code) DO NOTHING
                """),
                {"languages": languages}
            )

    def _insert_genres(self, df, conn):
        genres_list = []
        if "genres" in df.columns:
            for genres_val in df["genres"]:
                genres = self._parse_list_field(genres_val)
                genres_list.extend(genres)

        genres = sorted(set([g for g in genres_list if g]))
        if genres:
            conn.execute(
                text("""
                    INSERT INTO dim_genre (genre_name)
                    SELECT UNNEST(:genres)
                    ON CONFLICT DO NOTHING
                """),
                {"genres": genres}
            )

    def _insert_companies(self, df, conn):
        companies_list = []
        if "production_companies" in df.columns:
            for companies_val in df["production_companies"]:
                companies = self._parse_list_field(companies_val)
                companies_list.extend(companies)

        companies = sorted(set([c for c in companies_list if c]))
        if companies:
            conn.execute(
                text("""
                    INSERT INTO dim_production_company (company_name)
                    SELECT UNNEST(:companies)
                    ON CONFLICT DO NOTHING
                """),
                {"companies": companies}
            )

    def _insert_countries(self, df, conn):
        countries_list = []
        if "production_countries" in df.columns:
            for countries_val in df["production_countries"]:
                countries = self._parse_list_field(countries_val)
                countries_list.extend(countries)

        countries = sorted(set([c for c in countries_list if c]))
        if countries:
            conn.execute(
                text("""
                    INSERT INTO dim_production_country (country_name)
                    SELECT UNNEST(:countries)
                    ON CONFLICT DO NOTHING
                """),
                {"countries": countries}
            )

    def _insert_movies(self, df, conn):
        movies_df = df[[
            "movie_id", "title", "release_date",
            "revenue", "budget", "profit",
            "vote_average", "vote_count", "popularity"
        ]].drop_duplicates(subset=["movie_id"])
        
        movies_df["title"] = movies_df["title"].fillna("Unknown Title")
        movies_df = movies_df.dropna(subset=["movie_id"])
        movies_df["movie_id"] = movies_df["movie_id"].astype(int)
        
        numeric_cols = ["revenue", "budget", "profit", "vote_average", "vote_count", "popularity"]
        for col in numeric_cols:
            movies_df[col] = pd.to_numeric(movies_df[col], errors="coerce").fillna(0)
        
        movies_df["release_date"] = pd.to_datetime(movies_df["release_date"], errors="coerce")

        movies_df.to_sql("dim_movies_tmp", conn, if_exists="replace", index=False)
        
        conn.execute(text("""
            INSERT INTO dim_movies (movie_id, title, release_date, revenue, budget, profit, vote_average, vote_count, popularity)
            SELECT movie_id, title, release_date, revenue, budget, profit, vote_average, vote_count, popularity
            FROM dim_movies_tmp
            ON CONFLICT (movie_id) DO UPDATE SET
                title = EXCLUDED.title,
                release_date = EXCLUDED.release_date,
                revenue = EXCLUDED.revenue,
                budget = EXCLUDED.budget,
                profit = EXCLUDED.profit,
                vote_average = EXCLUDED.vote_average,
                vote_count = EXCLUDED.vote_count,
                popularity = EXCLUDED.popularity
        """))
        
        conn.execute(text("DROP TABLE dim_movies_tmp"))
        return movies_df

    def _populate_bridge_movie_genre(self, df, conn):
        bridge_data = []
        for _, row in df.iterrows():
            genres_val = row.get("genres")
            genres = self._parse_list_field(genres_val)
            for genre in genres:
                bridge_data.append({
                    "movie_id": int(row["movie_id"]),
                    "genre_name": genre
                })

        if not bridge_data:
            return
        
        bridge_df = pd.DataFrame(bridge_data)
        genre_mapping = pd.read_sql("SELECT genre_id, genre_name FROM dim_genre", conn)
        
        bridge_df = bridge_df.merge(genre_mapping, on="genre_name", how="inner")
        bridge_df = bridge_df[["movie_id", "genre_id"]].drop_duplicates()
        
        if len(bridge_df) > 0:
            bridge_df.to_sql("bridge_movie_genre_tmp", conn, if_exists="replace", index=False)
            conn.execute(text("""
                INSERT INTO bridge_movie_genre (movie_id, genre_id)
                SELECT movie_id, genre_id FROM bridge_movie_genre_tmp
                ON CONFLICT DO NOTHING
            """))
            conn.execute(text("DROP TABLE bridge_movie_genre_tmp"))

    def _populate_bridge_movie_language(self, df, conn):
        bridge_data = []
        for _, row in df.iterrows():
            lang = row.get("original_language")
            if pd.notna(lang):
                bridge_data.append({
                    "movie_id": int(row["movie_id"]),
                    "language_code": lang
                })
        
        if not bridge_data:
            return
        
        bridge_df = pd.DataFrame(bridge_data)
        language_mapping = pd.read_sql("SELECT language_id, language_code FROM dim_language", conn)
        
        bridge_df = bridge_df.merge(language_mapping, on="language_code", how="inner")
        bridge_df = bridge_df[["movie_id", "language_id"]].drop_duplicates()
        
        if len(bridge_df) > 0:
            bridge_df.to_sql("bridge_movie_language_tmp", conn, if_exists="replace", index=False)
            conn.execute(text("""
                INSERT INTO bridge_movie_language (movie_id, language_id)
                SELECT movie_id, language_id FROM bridge_movie_language_tmp
                ON CONFLICT DO NOTHING
            """))
            conn.execute(text("DROP TABLE bridge_movie_language_tmp"))

    def _populate_bridge_movie_production_company(self, df, conn):
        bridge_data = []
        for _, row in df.iterrows():
            companies_val = row.get("production_companies")
            companies = self._parse_list_field(companies_val)
            for company in companies:
                bridge_data.append({
                    "movie_id": int(row["movie_id"]),
                    "company_name": company
                })
        
        if not bridge_data:
            return
        
        bridge_df = pd.DataFrame(bridge_data)
        company_mapping = pd.read_sql("SELECT company_id, company_name FROM dim_production_company", conn)
        
        bridge_df = bridge_df.merge(company_mapping, on="company_name", how="inner")
        bridge_df = bridge_df[["movie_id", "company_id"]].drop_duplicates()
        
        if len(bridge_df) > 0:
            bridge_df.to_sql("bridge_movie_production_company_tmp", conn, if_exists="replace", index=False)
            conn.execute(text("""
                INSERT INTO bridge_movie_production_company (movie_id, production_company_id)
                SELECT movie_id, company_id FROM bridge_movie_production_company_tmp
                ON CONFLICT DO NOTHING
            """))
            conn.execute(text("DROP TABLE bridge_movie_production_company_tmp"))

    def _populate_bridge_movie_production_country(self, df, conn):
        bridge_data = []
        for _, row in df.iterrows():
            countries_val = row.get("production_countries")
            countries = self._parse_list_field(countries_val)
            for country in countries:
                bridge_data.append({
                    "movie_id": int(row["movie_id"]),
                    "country_name": country
                })
        
        if not bridge_data:
            return
        
        bridge_df = pd.DataFrame(bridge_data)
        country_mapping = pd.read_sql("SELECT country_id, country_name FROM dim_production_country", conn)
        
        bridge_df = bridge_df.merge(country_mapping, on="country_name", how="inner")
        bridge_df = bridge_df[["movie_id", "country_id"]].drop_duplicates()
        
        if len(bridge_df) > 0:
            bridge_df.to_sql("bridge_movie_production_country_tmp", conn, if_exists="replace", index=False)
            conn.execute(text("""
                INSERT INTO bridge_movie_production_country (movie_id, production_country_id)
                SELECT movie_id, country_id FROM bridge_movie_production_country_tmp
                ON CONFLICT DO NOTHING
            """))
            conn.execute(text("DROP TABLE bridge_movie_production_country_tmp"))
