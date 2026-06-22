---
name: git-workflow
description: Use when committing, naming a branch, or opening/merging a PR in this repo.
---

# Git and PR workflow

## Overview

Work moves from a branch to the default branch using Conventional Commits and
Conventional Branches. This skill covers commit format, branch naming, what
never gets committed, and the pre-PR gate.

## When to use

- Writing a commit message.
- Creating or naming a branch.
- Opening a PR.
- Before merging a PR.

## Quick reference

**Commits (Conventional Commits)**

- Format: `<type>(scope)(!): subject`.
- Types: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`, `build`, `ci`.
- Use `!` for a breaking change.
- Scopes track repo layout: `pipeline`, `web`, `db`, `docs`, `ci`.
- Subject is imperative, `<= 50` chars, no trailing period. Wrap body at ~72.
- If the changes were made by AI, end with a `Co-Authored-By` trailer. Include the
  model name, version, and git email (e.g. Claude Opus 4.8 noreply@anthropic.com)
- Keep commits small and focused: one logical change each. A schema change is
  one atomic commit (see the three-way mirror).

**Branches (Conventional Branches)**

- Format: `<type>/<short-description>`, e.g. `feat/edges-from-entry`,
  `fix/lazy-neon-client`. Type matches the commit type.
- Branch off the default branch for feature work, and keep branches
  short-lived.
- No force-push to shared branches. Rebase or amend only on your own
  unpushed/unshared history.

**Never commit**

- `data/` (raw dumps and generated artifacts), `.env`, any secret or
  credential, and build output. These are gitignored, so keep them so.
- If something must be tracked as an example, commit `.env.example`, never the
  real `.env`.

## PR checklist

Before opening or merging a PR, confirm:

- [ ] `uv run ruff format --check` is clean (run `uv run ruff format` to fix).
- [ ] `uv run ruff check` is clean.
- [ ] `uv run pytest` is green.
- [ ] `npm run check` (svelte-check) is clean.
- [ ] `npm run build` succeeds (Cloudflare adapter).
- [ ] The three-way schema mirror is updated in the same commit when the data
      model changes: `db/schema.sql` <-> `pipeline/.../model.py` <->
      `web/src/lib/types.ts` (see the `sql-schema-style` skill).
- [ ] `docs/DESIGN.md` and/or `CLAUDE.md` are updated when a decision or locked
      choice changes.
- [ ] Data-integrity invariants are respected: provenance, no invented facts,
      idempotency, bounded traversals (see `.claude/rules/data-integrity.md`).
