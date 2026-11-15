# API

Bearer authentication is required except `/health`. Request bodies are limited to 256 KiB; unknown fields fail. Authenticated `/v1/openapi.json` is the authoritative schema.

- POST `/v1/collections` `{name, visibility: "public"|"private"}`; GET lists your collections; DELETE `/v1/collections/{id}` removes content and vectors.
- POST `/v1/collections/{id}/ingest` `{urls:[...],max_pages:1000}` downloads that batch. To traverse a site, create a crawl with HoundCrawler, then import `{crawler_job:"...",crawler_profile:"my-crawler"}`. Omitting the profile imports a job from the same instance. GET `/v1/ingestions/{id}` reports progress; POST `/{pause|resume|cancel}` controls the local ingestion. Remote crawl lifecycle remains the caller's responsibility.
- POST `/v1/search` `{query,mode:"fast"|"balanced"|"deep",collections:[],providers:[],limit:10,include_domains:[],exclude_domains:[],include_contents:false,budget:{max_requests:40,max_tokens:100000,max_steps:8}}`. Optional language, content_types and publication dates filter known metadata only; unknown values are excluded when filtered. Results are candidate-limited, never exhaustive.
- GET `/v1/search/results/{snapshot}?offset=0&limit=10` pages a tenant-bound 15-minute immutable result snapshot without repeat upstream charges. The snapshot contains the original requested result limit.
- POST `/v1/contents` `{urls:[...],max_characters:24000,refresh:false}` returns source text, evidence kind, full hash and explicit truncation. POST `/v1/find-similar` `{url,...searchOptions}` uses local vectors when available, otherwise an explicitly labeled keyword approximation.
- PUT `/v1/profiles/{name}` configures an encrypted BYO provider; DELETE removes it. Keys are never returned. No client-selected arbitrary service URL is allowed.
- POST `/v1/answer` `{query,model_profile:"mine",...searchOptions}` generates source-cited claims. POST `/v1/research` accepts the same body and returns a durable job ID.
- GET `/v1/jobs/{id}` exposes state, result and used/reserved usage. GET `/v1/jobs/{id}/events?after=0` streams SSE. POST `/v1/jobs/{id}/{pause|resume|cancel}` controls research; resume may include a complete replacement budget object. In-flight upstream charges may complete after cancellation; new work is blocked. Unknown provider outcomes retain reservations.

Send Idempotency-Key for synchronous search/similar/answer and research creation. Reusing it with a different request fails. A synchronous execution interrupted before completion is inspectable and is not replayed automatically. Research resumes checkpoints; a crash after an upstream call but before its checkpoint can require another call and retains the first reservation. Inspect usage before resuming.
