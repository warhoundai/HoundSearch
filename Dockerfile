FROM python:3.12-slim-bookworm
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip install . && useradd --uid 10001 --create-home hound && mkdir /data && chown 10001:10001 /data
USER 10001:10001
ENV HOUNDSEARCH_STORAGE=/data
EXPOSE 8082
CMD ["houndsearch","serve","--host","0.0.0.0"]
