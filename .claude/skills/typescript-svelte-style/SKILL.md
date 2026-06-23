---
name: typescript-svelte-style
description: Use when writing or editing TypeScript or Svelte components in web/, adding a SvelteKit route or endpoint, or before running svelte-check.
---

# TypeScript / Svelte style (web/)

## Overview

Prettier with 2-space indentation (Google default), Google TypeScript Style
Guide as the baseline, single quotes, semicolons always, and trailing commas.
Precedence: project CLAUDE.md > this skill > Google guide.

## When to use

- Editing TypeScript or `.svelte` files under `web/`.
- Writing or changing a SvelteKit `+server.ts` endpoint or route.
- Adding or changing a type, interface, or shared graph type.
- Importing from `$lib` / `$lib/server`.
- Before running `svelte-check` (`npm run check`).

Not for pipeline Python: that lives under a separate Python style rule.

## Quick reference

- **Formatting:** 2 spaces, single quotes, semicolons always, trailing commas,
  ~80 columns. One
  variable per declaration. Braces on control blocks (single-line `if` may omit).
- **Exports:** named exports only, no default exports.
- **Imports:** `import type { X }` for type-only symbols. NEVER import
  `lib/server/*` from a client component (server-only loads from `+server.ts` /
  `*.server.ts`). No `namespace`, `require()`, `<reference>`.
- **Types:** `any` is forbidden, use `unknown` and narrow. Avoid `{}`. Prefer
  `interface` for object shapes. `readonly` on never-reassigned props. Optional
  `field?: T` over `field: T | undefined`. No `@ts-ignore` / `@ts-expect-error`.
- **Naming:** `lowerCamelCase` for vars/functions, `UpperCamelCase` for
  types/classes, `CONSTANT_CASE` for module constants. No `I`-prefix. Whole-word
  abbreviations (`loadHttpUrl`).
- **Equality / coercion:** `===` / `!==` always, `== null` only for null plus
  undefined. Coerce with `String()` / `Number()` / `Boolean()` / `!!`, never
  wrapper `new`. `Number()` + `Number.isFinite()`, not `parseInt`.
- **Control flow:** guard clauses, early returns, nesting <= 3 levels. `while`
  loops need a max-iteration or deadline bound. Throw `new Error(...)` only,
  never a string.
- **Disallowed:** `var`, `const enum`, `eval()` / `Function(string)`, prototype
  modification, `with`, `debugger`.
- **Svelte 5:** use runes (`$state`, `$derived`, `$props`, `$effect`), not legacy
  `export let` / reactive `$:`. `svelte-check` must report 0 errors.

## SvelteKit specifics

- Endpoints return via `json()` and fail via `error()` from `@sveltejs/kit`.
- Type handlers with `RequestHandler` from `./$types`.
- `web/src/lib/types.ts` mirrors `db/schema.sql`. If one changes, change both.
- Keep the Neon client lazy (`lib/server/db.ts`) so the build does not need
  `DATABASE_URL`.
- Before committing: `npm run check`.

## Full rules

Read `references/typescript-style.md` before a substantial change or when the
quick reference is ambiguous.
