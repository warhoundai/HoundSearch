# Contributing

Use Python 3.12+, install the pinned public HoundCrawler dependency and this project with its dev extra. Start an isolated PostgreSQL database named houndsearch_test, set HOUNDSEARCH_TEST_DATABASE_URL, and run pytest -q and node --test sdk/js/*.test.mjs. Semantic tests require the optional extra, explicit model provisioning and pgvector; they must never silently download or skip when the profile is required.

Use controlled fixtures, test failure/recovery and cross-tenant access, document schema/API changes, and preserve evidence provenance. Do not commit credentials, customer documents, private WarHound source or model weights. Contributions are Apache-2.0; maintainers review changes through pull requests. Read CODE_OF_CONDUCT.md and SECURITY.md.
