---
name: project-backlog
description: Use when adding, updating, or triaging etymyriad backlog/roadmap items on the private GitHub Project (van-riper/projects/4). This covers gh project commands, field/option IDs, and the Status/Priority/Area/Phase workflow.
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
  Backlog 4538b7fa | To Do f75ad846 | In Progress 47fc9ee4 | Done 98236657

Priority PVTSSF_lAHOA9qC1c4BdaByzhYBMOM
  High 596255b5 | Medium c7eff115 | Low 647e2fc9

Area     PVTSSF_lAHOA9qC1c4BdaByzhYATPI
  etl ae60e295 | web c5c838f4 | db 60184dbb | docs 481a6113

Phase    PVTSSF_lAHOA9qC1c4BdaByzhYAT4Y
  Phase 1 b9b7a6b2 | Phase 2 dc009842 | Phase 3 3b57ef55
  Phase 4 4aaa199f | Phase 5 96259b6e | Phase 6 866b5bde
  Cross-cutting 9c9ece2f
```

If any `item-edit` call below returns a "not found" GraphQL error, the IDs
have drifted (e.g. a field was deleted/recreated) - re-fetch first, don't
guess:

```sh
gh project field-list 4 --owner van-riper --format json
```

## Add a new item

Every item title is prepended with a unique, sequential numeric ID
(`1: ...` up to the current highest - check first, don't assume):

```sh
gh project item-list 4 --owner van-riper --format json --limit 100 \
  | jq -r '.items[].title' | grep -oE '^[0-9]+' | sort -n | tail -1
```

Use that number + 1 as the new item's prefix:

```sh
next=$(( $(gh project item-list 4 --owner van-riper --format json --limit 100 \
  | jq -r '.items[].title' | grep -oE '^[0-9]+' | sort -n | tail -1) + 1 ))

item_id=$(gh project item-create 4 --owner van-riper \
  --title "$next: ..." --body "..." --format json | jq -r '.id')

gh project item-edit --project-id PVT_kwHOA9qC1c4BdaBy --id "$item_id" \
  --field-id PVTSSF_lAHOA9qC1c4BdaByzhX7yZY \
  --single-select-option-id 4538b7fa   # Status: Backlog (default)
```

Set Priority/Area/Phase the same way, swapping field-id/option-id from the
table above. Default new items to **Backlog** unless you're starting the
work in this same session (then To Do / In Progress).

One pre-existing item, "Seed language table lang_family", has no number -
a gap from before this convention was written down here, not a sign the
numbering is broken. Leave it as-is unless asked to fix it.

## Update an existing item

Find its `item-id` first (title match), then run the same `item-edit`
pattern with the new option-id:

```sh
gh project item-list 4 --owner van-riper --format json \
  | jq '.items[] | select(.title | test("keyword"; "i"))'
```

Move to In Progress when you start non-trivial work on an item, Done once
it ships.

To edit an item's **title or body** (`--title`/`--body`), pass the
**content ID** (`DI_...`, from `.content.id` in the jq query above), not
the item ID (`PVTI_...`). Passing the item ID exits 0 and prints a usage
error to stdout instead of failing loudly - check the output, don't assume
success from the exit code alone.

## Split a placeholder item into finer items

When a phase's bundled placeholder (e.g. "16: Word pages, backtraces, and
SEO breakdowns (rest of Phase 3)") starts active work, replace it with
individually-tracked items rather than editing it in place:

1. Create the finer items (see "Add a new item" above), same Phase/Area,
   Status set to how far each has actually progressed.
2. Retire the placeholder - archive rather than delete, so the split is
   recoverable if it turns out wrong:
   ```sh
   gh project item-archive 4 --owner van-riper --id <placeholder-item-id>
   ```
3. Flag that the project README's "Where things stand" note is now stale.
   Drafting the replacement text is fine, but setting it needs
   `gh project edit --readme`, which is blocked for agents - hand the
   command to the user with `!`.

## Permission gate (`dcg`)

Read-only (`view`/`list`/`item-list`/`field-list`) and
`item-create`/`item-edit`/`item-add`/`field-create`/`item-archive`/
`item-delete` all work from this repo. `field-delete` and the top-level
`gh project edit` (readme/title/visibility) are blocked by the user's own
choice - hand the command to the user with `!` instead of retrying or
asking for the grant again.

## Don't

- Don't re-add backlog/roadmap detail to `CLAUDE.md` or recreate
  `docs/ROADMAP.md` - the project is the single source of truth.
- Don't convert Draft items to real Issues or suggest a linked/private repo
  - considered and declined 2026-07-15 (Status/Priority/Area/Phase and the
  Backlog->Todo->In Progress->Done flow already work fully on Drafts).
- Don't rename field options via `gh` - there's no rename command; it's
  field-delete + field-create + re-tagging every item, and `field-delete`
  needs the user's go-ahead each time.
