FROM python:3.12

RUN pip install uv

WORKDIR /app
ENV PYTHONPATH=/app

COPY /pyproject.toml /uv.lock ./
RUN uv sync --frozen

COPY . .

RUN apt-get update && apt-get install -y postgresql-client

COPY /worker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]