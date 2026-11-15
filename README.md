# HoundSearch

**Self-hosted search and evidence-grounded research for AI agents.**

[![Checks](https://github.com/warhoundai/HoundSearch/actions/workflows/checks.yml/badge.svg)](https://github.com/warhoundai/HoundSearch/actions/workflows/checks.yml)
[![Apache 2.0](https://img.shields.io/badge/license-Apache%202.0-black)](LICENSE)

Search your own indexed pages with PostgreSQL full-text search, optionally combine local neural retrieval and reranking, and explicitly connect your own Exa, Brave, Serper or SearXNG account. Build answers and resumable research from fetched evidence using your own model. No WarHound keys, hosted quota or mandatory paid provider.

**0.1.0rc1 is a preview**, not a claim of Exa parity or a proprietary global web index. [Verification](docs/verification.md) distinguishes local tests, synthetic scale checks, optional model qualification and external provider acceptance.

## Run locally

Requires Python 3.12+, Docker and Compose.

```bash
git clone https://github.com/warhoundai/HoundSearch.git
cd HoundSearch
python -m venv .venv
. .venv/bin/activate
pip install .
python scripts/configure.py
docker compose up --build -d
```

Read your generated owner-only `.env` locally. Use a key in HOUNDSEARCH_API_KEYS as `HOUNDSEARCH_API_KEY`; never commit it. The API binds to `127.0.0.1:8082`. No upstream key is required for your local index. A new index is empty until you ingest pages.

```python
import os
from houndsearch.client import Client
with Client('http://127.0.0.1:8082', api_key=os.environ['HOUNDSEARCH_API_KEY']) as client:
    collection = client.collection('Public documentation')
    ingestion = client.ingest(collection['id'], ['https://example.com/'])
    print(ingestion)  # poll GET /v1/ingestions/{id} until completed
    print(client.search('example', collections=[collection['id']]))
```

## Agent interfaces

- REST: `/v1/search`, `/v1/contents`, `/v1/find-similar`, `/v1/answer`, `/v1/research`.
- Collections and durable ingestion from public URLs or a configured HoundCrawler job.
- Tenant-isolated profiles, results, snapshots, jobs, SSE and pause/resume/cancel.
- Python SDK; dependency-free JavaScript client in `sdk/js/index.mjs`; CLI and MCP stdio (`houndsearch mcp`).
- Authentication and OpenAPI at `/v1/openapi.json` using your own instance bearer key.

Fast mode uses keyword search; balanced adds local vectors when explicitly enabled; deep additionally reranks the first 32 candidates when configured. External providers are contacted only when selected or configured as the primary provider. No silent paid fallback or retry.

Answers require a named BYO model profile. Each returned claim has an exact source quote and offsets; invalid quotes are discarded and absent evidence causes abstention. Quote presence is checked mechanically; semantic claim truth is not guaranteed. Research checkpoints its query plan and progress, with atomic shared request/token/configured-cost reservations across calls.

See [API](docs/api.md), [self-hosting](docs/deployment.md), [architecture and models](docs/architecture.md), [provider setup](docs/providers.md), [security](SECURITY.md), [contributing](CONTRIBUTING.md) and [license](LICENSE).
