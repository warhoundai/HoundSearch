# Security policy

Report vulnerabilities privately to accounts@warhoundai.com; never post keys or customer content in public issues. This self-hosted preview is one operator trust domain, not a fully hardened adversarial multi-tenant hosting service. Isolate deployments for untrusted customers.

All API operations except health require an instance key. Collection, document, profile, snapshot and job access is tenant-bound. Public fetches use the public HoundCrawler network policy: pinned public DNS, per-redirect checks, bounded decoding and no cross-origin credential forwarding. No shell, filesystem or CDP API is exposed. Operator-allowlisted upstreams are trusted configuration; malicious operator configuration can leak data. Use TLS, egress restrictions and workload least privilege.

Provider profiles are Fernet-encrypted. Source text, artifacts and database backups need operator-managed at-rest encryption. Query consent gates prevent automatic private-index transmission to upstreams, but do not replace your data-handling policy. Retrieved text is untrusted evidence; source quote presence is checked, while claim entailment and prompt-injection immunity are not guaranteed.

Atomic usage reservations bound new work across workers. Unknown paid outcomes remain reserved; provider billing is not exactly once. Cancellation blocks subsequent calls but cannot undo in-flight provider charges. User-supplied configured prices are estimates, not verified invoices. No WarHound keys are distributed.
