---
name: project-backlog
description: Use when adding, updating, or triaging etymyriad backlog/roadmap items on the private GitHub Project (van-riper/projects/4). This covers gh project commands, field/option IDs, and the Status/Priority/Target/Blocked/Decision/Active workflow.
---

## Where the backlog lives

Project #4, owner `van-riper`, all-Draft items (no linked repo, Issues
disabled on `van-riper/etymyriad`). No `docs/ROADMAP.md` exists - the
project's README field holds the phase/milestone narrative, its items hold
the itemized backlog. See `CLAUDE.md`'s "Project board & backlog workflow"
section for the human-facing summary; this skill has the IDs to act on it.

## Fields and IDs

```
PROJECT_ID=PVT_kwHOA9qC1c4BdaBy

Status   PVTSSF_lAHOA9qC1c4BdaByzhX7yZY
  Open 4538b7fa | Done 98236657

Priority PVTSSF_lAHOA9qC1c4BdaByzhYBMOM
  High 596255b5 | Medium c7eff115 | Low 647e2fc9

Target   PVTSSF_lAHOA9qC1c4BdaByzhYEVOc
  Now b610a379 | Next 694f47a5 | Later 211578d0 | Someday 3925d590

Blocked  PVTSSF_lAHOA9qC1c4BdaByzhYEVOg
  Blocked 2c1b1285

Decision PVTSSF_lAHOA9qC1c4BdaByzhYEVOk
  Decision 07c3cda8

Active   PVTSSF_lAHOA9qC1c4BdaByzhYEVOo
  Active e0ea67d8
```

Blocked/Decision/Active are single-value flags: set (`on`) or unset
(`off`/absent), not multi-option fields.

These values live in `project-backlog.conf.sh` at the repo root; `scripts/lib.sh`
loads them for scripts below, exposing them as `open`/`high`/`now`/`blocked` keys.
This separation keeps consumer-specific configuration separate from the generic
skill code, allowing the skill to be extracted into a standalone plugin later. If
any script call returns a "not found" GraphQL error, the IDs have drifted (e.g. a
field was deleted/recreated) - refresh and update `project-backlog.conf.sh` before
guessing:

```sh
scripts/refresh-ids.sh
```

## Scripts

Use `scripts/*.sh` instead of retyping raw `gh project` commands - same
calls, one invocation instead of a multi-line block generated fresh each
time:

| Script                    | Purpose                                         |
| ------------------------- | ------------------------------------------------ |
| `scripts/next-number.sh`  | Prints the next sequential ticket number.        |
| `scripts/create-item.sh`  | `<title> <body> [priority] [target]` - creates an item as Status: Open and tags priority/target in one call. Field args default to `low`/`later`. |
| `scripts/set-fields.sh`   | `<item-id> [status] [priority] [target] [blocked] [decision] [active]` - updates fields on an existing item; pass `-` to leave a field unchanged. `blocked`/`decision`/`active` take `on`/`off`/`-`. |
| `scripts/find-item.sh`    | `<title-keyword-regex>` - prints matching items as JSON, including `.id` and `.content.id`. |
| `scripts/edit-item.sh`    | `<content-id> [title] [body]` - rewrites an item's title/body; pass `-` to leave a field unchanged. Uses the `.content.id` (`DI_...`), not the item id. |
| `scripts/archive-item.sh` | `<item-id>` - archives a placeholder item.       |
| `scripts/refresh-ids.sh`  | Prints current field/option IDs, for when they've drifted. |
| `scripts/set-readme.sh`   | `<readme-file>` - sets the project README from a file's contents. |

Status/priority/target/blocked/decision/active arguments are the map
keys from `scripts/lib.sh` (e.g. `done`, `high`, `now`, `on`), not raw
option IDs.

## Add a new item

Every item title is prepended with a unique, sequential numeric ID
(`1: ...` up to the current highest):

```sh
next=$(scripts/next-number.sh)
scripts/create-item.sh "$next: ..." "body text"
```

`create-item.sh` always sets Status: Open (there's no separate Backlog
status anymore). Priority/target default to `low`/`later` if omitted;
pass them explicitly for items you're starting in this same session,
e.g.:

```sh
scripts/create-item.sh "$next: ..." "body text" medium now
```

One pre-existing item, "Seed language table lang_family", has no number -
a gap from before this convention was written down here, not a sign the
numbering is broken. Leave it as-is unless asked to fix it.

## Update an existing item

Find its item first (title match):

```sh
scripts/find-item.sh "keyword"
```

Then update fields with its `.id` (the `PVTI_...` item id):

```sh
scripts/set-fields.sh <item-id> - - now - - on
```

Set Target to `now` and the Active flag on when you start non-trivial
work on an item, Status to `done` once it ships.

To edit an item's **title or body**, use `scripts/edit-item.sh
<content-id> [title] [body]`, with the **content ID** (`DI_...`, from
`.content.id` in `find-item.sh`'s output), not the item ID (`PVTI_...`).
Passing the item ID exits 0 and prints a usage error to stdout instead of
failing loudly - check the output, don't assume success from the exit
code alone.

## Split a placeholder item into finer items

When a phase's bundled placeholder (e.g. "16: Word pages, backtraces, and
SEO breakdowns (rest of Phase 3)") starts active work, replace it with
individually-tracked items rather than editing it in place:

1. Create the finer items (see "Add a new item" above), Target set to
   how urgently each should be picked up, Status Open (Done if a piece
   already shipped).
2. Retire the placeholder - archive rather than delete, so the split is
   recoverable if it turns out wrong:
   ```sh
   scripts/archive-item.sh <placeholder-item-id>
   ```
3. Flag that the project README's "Where things stand" note is now stale.
   Draft the replacement text, save it to a file, then set it:
   ```sh
   scripts/set-readme.sh <path-to-readme.md>
   ```

## Permission gate (`dcg`)

`dcg`'s default rule (`block-gh-non-view`) blocks every non-read-only `gh`
subcommand, `gh project item-create`/`item-edit`/`item-archive`/etc.
included - despite being safe, non-destructive project-board writes, they
aren't in dcg's read-only allowlist (`view`/`list`/`status`/`diff`/
`checks`). `.claude/settings.local.json` (gitignored, per-machine) has a
permission rule allowlisting `Bash`/`Write`/`Edit` on
`.claude/skills/project-backlog/scripts/**`, so invoking the scripts above
avoids that block on this machine; a fresh clone or another dev's session
without that same local rule will still hit it and need to hand the raw
`gh` command to the user with `!`.

`field-delete` has no such allowlist entry and stays blocked - hand that
command to the user with `!` instead of retrying or asking for the grant
again. `gh project edit` (readme/title/visibility) is wrapped by
`scripts/set-readme.sh` for the readme case; title/visibility changes
still have no script and should go to the user with `!`.

## Don't

- Don't re-add backlog/roadmap detail to `CLAUDE.md` or recreate
  `docs/ROADMAP.md` - the project is the single source of truth.
- Don't convert Draft items to real Issues or suggest a linked/private repo
  - considered and declined 2026-07-15 (Status/Priority/Target/Blocked/
  Decision/Active already work fully on Drafts).
- Don't rename field options via `gh` - there's no rename command; it's
  field-delete + field-create + re-tagging every item, and `field-delete`
  needs the user's go-ahead each time.
