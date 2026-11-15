# Verification record

Initial local suite: **21 passed, 2 opt-in qualifications skipped** on 2026-11-15 against an isolated PostgreSQL database. Covers index/reindex, tenant isolation, snapshots, idempotency, concurrent request ceilings, unknown usage, committed cost-overrun pauses, encryption/endpoint policy, recovered research leases, cancellation, fabricated-quote rejection, abstention ingestion checkpoints, all four provider wire fixtures and paid-failure reservation retention.

Semantic, scale, container and provider qualification are separate gates; see GitHub Actions and its artifacts for actual outcomes. No Exa/Firecrawl comparison or live paid-provider acceptance is claimed without dedicated user-owned keys. Synthetic retrieval relevance is not evidence of open-web search parity.

The 100,000-document synthetic keyword-index fixture passed 200 held-out document-ID lookups with 100% top-1 matches and about 3.37 ms median / 3.46 ms p95 query time on a 2-CPU runner. This checks index capacity and deterministic lookup, not general semantic relevance. See [raw scale record](scale-result.json).

Real pinned local embeddings, pgvector retrieval and cross-encoder reranking passed a three-document controlled semantic fixture. See [raw semantic record](semantic-result.json) and https://github.com/warhoundai/HoundSearch/actions/runs/43692531096 . This does not qualify a 100,000-document vector corpus or real-world web relevance.

Core, dependency/source audits, package build and authenticated production-container retrieval passed at 513a8a1c1c75ef00c33969cb65c07bad705e02ca: https://github.com/warhoundai/HoundSearch/actions/runs/43693181149 . Later context-budget compression has an additional local regression test; final release CI records remain the source of truth.
