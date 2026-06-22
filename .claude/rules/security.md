# Security & secrets rules

Operative, self-contained ruleset for handling secrets, untrusted input, and
the public API surface. The dataset is public and read-only, so the real risk
sits in the pipeline write-path and any future mutating endpoints. Markers:
**(H)** = house preference, **(P)** = project-specific.

## Secrets

- **Never commit `.env`.** It is gitignored, so keep it that way. Only
  `.env.example` (placeholder values, no real secrets) is tracked.
- `DATABASE_URL` and other credentials come **only from the environment**, never
  hardcoded in source, tests, or fixtures.
- In SvelteKit, only `$env/static/public` (and `PUBLIC_`-prefixed vars) may reach
  the **client bundle**. `$env/static/private` and `$env/dynamic/private` are
  **server-only** and must be imported solely from code under
  `web/src/lib/server/`. Never import a private env module into a component or
  shared (non-`server/`) module.
- Production secrets live in **Cloudflare** (Pages project env / bindings), not
  in the repo. Local dev reads from `.env`.
- **Never log secrets or full connection strings.** Redact `DATABASE_URL` in any
  error, log line, or debug dump. Log the host or a fixed label at most.

## SQL injection

- **Always parameterize.** Never interpolate request data into SQL. See the
  `sql-schema-style` skill (Query safety) for the concrete mechanism: psycopg
  `%s` parameters in Python, the Neon tagged-template in the web app.
- No f-strings or template literals carrying raw request values into a query.

## Input validation

- **Validate and clamp every request parameter at the boundary**, before it
  reaches a query. The `depth` clamp to `1..4` in
  `web/src/routes/api/word/[lang]/[headword]/+server.ts` is the canonical
  pattern: coerce, bounds-check, fall back to a safe default for non-finite
  input.
- Bound and length-limit `lang` and `headword`: reject anything implausibly long
  or malformed (e.g. `lang` outside the expected short-code shape).
- **Reject malformed input with a 4xx** (`400`). Do not pass questionable input
  downstream to a query or the pipeline. A missing lexeme is a `404`.

## API hardening

- **Return generic error messages.** No stack traces, SQL text, or internal
  detail to clients. Use SvelteKit `error(status, message)` with a safe message,
  and keep diagnostics server-side.
- Consider **rate limiting** on public endpoints (Cloudflare rules or an
  in-route guard) before launch, since the API is unauthenticated.
- **HTTPS only.** Cloudflare enforces TLS. Do not add plaintext fallbacks.

## Supply chain

- **Commit lockfiles** (`uv.lock`, `package-lock.json`) so builds are
  reproducible.
- Keep dependencies **minimal and justified.** Review and audit a package before
  adding it, and prefer the standard library or an existing dep.
- The data is public and read-only, so the main risk surface is the pipeline
  **write-path** and any future **mutating endpoints**. Scrutinize anything that
  writes to Postgres or accepts input that reaches a write.
