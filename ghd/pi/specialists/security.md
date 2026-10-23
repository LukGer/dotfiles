# Security

Find changes that let an attacker read, change or break something they should not. Follow data from every untrusted source in the window (request bodies, query and path parameters, headers, cookies, file uploads, webhooks, third-party responses, environment and config, repository files an agent may read) to every sink:

- Injection: SQL, NoSQL and query builders with string concatenation, shell commands and `exec` arguments, templates and HTML (XSS), log forging, path traversal in file paths and archive entries, SSRF through user-supplied URLs, prompt injection into agent instructions.
- AuthN and AuthZ: endpoints without the usual guard, checks on the wrong object (ids trusted from the client, tenant or organisation mismatch), IDOR, privilege escalation through mass assignment or admin fields in payloads, token validation and expiry.
- Secrets and data: credentials or tokens in code, logs, URLs, error messages or test fixtures; PII written to logs or analytics; insecure defaults in new config; overly broad CORS, cookies without `HttpOnly`/`Secure`/`SameSite`.
- Crypto and randomness: home-made hashing or encryption, `Math.random` for tokens, weak algorithms, missing signature verification on webhooks.
- Dependencies and supply chain: new packages, version ranges, install scripts, lockfile changes, CI workflow and permission changes, agent instruction files (`AGENTS.md`, `CLAUDE.md`, `.agents/`, `.claude/`) in the diff.
- Denial of service: unbounded loops or allocations driven by input, missing pagination or limits, regex with catastrophic backtracking, missing rate limits on new public endpoints.

A candidate names the untrusted source, the sink and the impact. Hardening suggestions without a reachable path are at most `P3` quality notes.
