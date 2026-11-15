# Bring your own providers

Instance keys authenticate HoundSearch; upstream keys belong to your own provider account. They are different credentials. No upstream is enabled by default. Configure profiles using PUT `/v1/profiles/{name}` over TLS, or HOUNDSEARCH_PROFILES as tenant-to-profile JSON in your secret store. Never place keys in URLs, prompts, logs, repository files or browser code.

Search profile kinds: exa, brave, serper (key required), searxng (your self-hosted endpoint, optional key). Set providers by profile name in requests or HOUNDSEARCH_PRIMARY_PROVIDER. Fixed cloud provider endpoints cannot be overridden. SearXNG, crawler and OpenAI-compatible endpoints must exactly match HOUNDSEARCH_TRUSTED_ENDPOINTS configured by the operator.

Model kinds: gemini with your key and supported model; vertex with project, location, model and operator workload identity; openai with your own allowlisted endpoint/model/key. Vertex identity is instance-scoped: isolate deployments for tenants needing separate IAM identities. Model availability is not inferred or automatically substituted. Optional vertex dependencies install with `pip install '.[vertex]'`.

A model profile may contain pricing; use the HoundCrawler pricing schema with current source/provenance. A search profile may contain request_cost_usd. Dollar ceilings require configured prices for every external call; these are operator estimates, not provider invoices. Missing token counters retain conservative reservations. Usage includes reasoning tokens when returned by the provider. No WarHound usage fee is charged by this software.

Private collection queries/source text require explicit external_private_consent before upstream search/model transmission. This does not make third-party processing private; review your provider terms.

External adapter correctness has local fixtures. Live acceptance and Firecrawl/Exa comparisons require separately supplied user-owned keys and are not claimed without recorded evidence.
