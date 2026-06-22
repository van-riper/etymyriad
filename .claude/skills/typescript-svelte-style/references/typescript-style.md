# TypeScript / Svelte style rules (web/)

Operative, self-contained ruleset for TypeScript and Svelte in this repo.
Baseline is the
[Google TypeScript Style Guide](https://google.github.io/styleguide/tsguide.html).
This file is what to follow when they differ. Markers: **(H)** = house
preference, stricter than Google. **(P)** = project-specific.

Precedence: project CLAUDE.md > this file > Google guide.

## Formatting

- Format with **Prettier** (SvelteKit defaults). **Tabs** for indentation **(P,
  overrides Google's 2 spaces)**, matching SvelteKit's generated code.
- Single quotes, and **semicolons always** (never rely on ASI).
- One variable per declaration (no `let a = 1, b = 2`).
- Braces on all control blocks. A single-line `if (x) doFoo();` may omit them.
- Target ~80 columns to stay consistent with the Python side **(H)**.

## Imports & exports

- **Named exports only.** No default exports.
- `import type { X }` when a symbol is used only as a type.
- Use `$lib` / `$lib/server` aliases. **Never import `lib/server/*` from a client
  component**: server-only code loads only from `+server.ts` / `*.server.ts` **(P)**.
- No `namespace`, `require()`, or `<reference>` directives.

## Naming

- variables/params/functions/methods/properties `lowerCamelCase`,
  classes/interfaces/types/enums/type-params `UpperCamelCase`, module-level
  constants and enum members `CONSTANT_CASE`.
- No `I`-prefix on interfaces. No leading/trailing underscores. Use the
  `private` modifier, not `#private` fields.
- Abbreviations are whole words: `loadHttpUrl`, not `loadHTTPURL`.
- Apply the house **S-I-D**, **units-in-names**, **plural-for-collections**, and
  **no-abbreviation** rules. Single-letter names only in scopes under ~10 lines **(H)**.

## Type system

- Let the compiler infer trivial types. Annotate exported function parameters
  and returns (and any non-obvious return).
- **`any` is forbidden.** Use `unknown` and narrow. Avoid the `{}` type
  (`Record<string, T>`, `object`, or `unknown` instead).
- Prefer `interface` for object shapes over type aliases. `T[]` for simple
  element types, `Array<T>` for complex ones.
- `readonly` on properties never reassigned after construction. Prefer immutable
  data.
- Optional `field?: T` over `field: T | undefined`. No nullable type aliases
  (`type X = T | null`). Handle null where it originates, not across layers.
- Type assertions: `as T` only, sparingly, with a comment when not obviously
  safe. Double-cast through `unknown` only when unavoidable. Prefer a `: Type`
  annotation on object literals over `as Type`.
- Never use `@ts-ignore` / `@ts-expect-error` to silence a real error.

## Equality & coercion

- `===` / `!==` always, `== null` only to test null and undefined together.
- Coerce with `String()`, `Boolean()`, `Number()`, `!!`, or template literals,
  never wrapper `new`. Use `Number()` + `Number.isFinite()`, not `parseInt`, for
  base-10.

## Functions

- `function foo() {}` for named top-level functions, arrow functions for
  callbacks and expressions. No `function` expressions that use `this`.
- Concise arrow body when the value is used, block body otherwise.
- Rest params (`...args`), not `arguments`. Spread, not `.apply()`. Simple
  default params (no side effects). Do not `.bind()`.

## Control flow & errors

- Guard clauses, early returns, nesting **≤ 3 levels** **(H)**.
- `for...of` over index loops and `.forEach()`. Use `for...in` only with
  `Object.keys()` / `hasOwnProperty`.
- A `while` loop must carry a max-iteration or deadline bound **(H)**.
- Throw `new Error(...)` (or a subclass) only, never a string. Do not use
  exceptions for control flow, and keep `try` blocks tight.

## Disallowed

`var`, `const enum`, `eval()` / `Function(string)`, prototype modification,
`with`, and `debugger`.

## Comments & JSDoc

- `/** ... */` JSDoc on exported/public APIs, `//` for implementation notes.
- Explain **why, not what**. Tags carry owner + date **(H)**:
  `// TODO(finn, 2026-06): ...`.

## Svelte 5 specifics

- Use runes: `$state`, `$derived`, `$props`, `$effect`. Do not use the legacy
  `export let` / reactive-`$:` patterns in new components.
- `svelte-check` must report **0 errors** before commit (`npm run check`).

## SvelteKit specifics (P)

- In endpoints, return via `json()` and fail via `error()` from `@sveltejs/kit`,
  and type handlers with `RequestHandler` from `./$types`.
- `web/src/lib/types.ts` mirrors `db/schema.sql`. If one changes, change both.
- Keep the Neon client lazy (`lib/server/db.ts`) so the build does not need
  `DATABASE_URL`.
- Before committing: `npm run check`.
