CREATE TABLE IF NOT EXISTS dim_language (
    id SERIAL PRIMARY KEY,
    language_code TEXT UNIQUE
);

CREATE TABLE IF NOT EXISTS dim_status (
    id SERIAL PRIMARY KEY,
    status TEXT UNIQUE
);

CREATE TABLE IF NOT EXISTS fact_movies (
    movie_id INT PRIMARY KEY,
    title TEXT,
    release_date DATE,
    revenue NUMERIC,
    budget NUMERIC,
    profit NUMERIC,
    vote_average NUMERIC,
    vote_count INT,
    popularity NUMERIC,

    dim_language_id INT REFERENCES dim_language(id),
    dim_status_id INT REFERENCES dim_status(id),

    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS staging_movies (
    movie_id INT,
    title TEXT,
    release_date DATE,
    revenue NUMERIC,
    budget NUMERIC,
    profit NUMERIC,
    vote_average NUMERIC,
    vote_count INT,
    popularity NUMERIC,
    original_language TEXT,
    status TEXT
);

CREATE INDEX IF NOT EXISTS idx_fact_release_date ON fact_movies(release_date);
CREATE INDEX IF NOT EXISTS idx_fact_language ON fact_movies(dim_language_id);