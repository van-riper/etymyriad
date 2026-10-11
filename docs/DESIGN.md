# Design

_Last updated: 2026-10-10_

The visual and interaction guide for agents working on the web UI. It records
how the UI looks and behaves today. A full reskin with new UI/UX is planned, so
treat this as the current baseline: match it when you touch the UI, and don't
start a new visual direction in passing. The system, the data model, and the ETL
are in [`ARCHITECTURE.md`](ARCHITECTURE.md).

## 1. Principles

These hold whatever the skin looks like.

- One word at a time. The screen shows a bounded tree around a focus word, never
  the whole graph. Hidden children appear as a "+N more" marker.
- Deterministic layout. The same slice always draws the same picture: no
  physics, no random placement.
- Ancestors sit left of the focus and descendants right of it. Every arrow
  points from ancestor to descendant, so arrows always point right.
- A reconstructed form shows a leading `*` everywhere a headword appears
  (`displayHeadword()` in `web/src/lib/tree/headword.ts`).
- Sources stay one click away. The detail card links each word to its Wiktionary
  page.
- One full-viewport canvas with floating chrome. The page never scrolls.

## 2. Color

The palette is [Flexoki](https://github.com/kepano/flexoki). Colors are the only
design tokens; they live in `web/src/lib/theme/variables.css`. Components
reference the tokens, never raw hex values.

| Token             | Light     | Dark      | Used for                       |
| ----------------- | --------- | --------- | ------------------------------ |
| `--bg`            | `#fffcf0` | `#100f0f` | canvas, popover lists          |
| `--bg-2`          | `#f2f0e5` | `#1c1b1a` | panels, nodes, inputs, toasts  |
| `--ui-border`     | `#dad8ce` | `#343331` | every 1 px border, node stroke |
| `--tx-3`          | `#b7b5ac` | `#575653` | faint borders (edge labels)    |
| `--tx-2`          | `#6f6e69` | `#878580` | muted text, edges, arrowheads  |
| `--tx`            | `#100f0f` | `#cecdc3` | body text                      |
| `--accent`        | `#205ea6` | `#4385be` | info toasts                    |
| `--focus`         | `#af3029` | `#d14d41` | the focus node                 |
| `--danger`        | `#af3029` | `#d14d41` | errors, redlink nodes          |
| `--success`       | `#66800b` | `#879a39` | success toasts                 |
| `--warning`       | `#bc5215` | `#da702c` | warning toasts                 |
| `--rel-borrowing` | `#5e409d` | `#8b7ec8` | borrowing edge labels          |
| `--rel-weak`      | `#a02f6f` | `#ce5d97` | mention edge labels            |

Theme modes are light, dark, and system (shown as "Auto"). The toggle cycles
through them, and the choice persists in `localStorage` under `etymyriad-theme`.
The resolved theme lands on `<html data-theme>`. An inline script in
`web/src/app.html` sets it before first paint, so the page never flashes the
wrong theme. Toasts (svelte-sonner) follow the theme.

Spacing, radii, and font sizes are not tokens. Each component sets literal
values in its own `<style>` block. The common radii are 6 px for nodes and small
controls, 8 px for panels, and 999 px for pills.

## 3. Typography

| Role           | Face                  | Notes                        |
| -------------- | --------------------- | ---------------------------- |
| Body and UI    | Inter (400 to 700)    | Noto Sans faces as fallbacks |
| Landing title  | Libre Baskerville 700 | 2.5rem, used nowhere else    |
| Language codes | monospace             | inputs, list items, version  |

The body stack adds eleven Noto Sans historic-script faces (Gothic, Old Italic,
Avestan, and others) so ancient headwords render. Rarer scripts fall back to
tofu by choice.

| Element                 | Size     |
| ----------------------- | -------- |
| Error status code       | 3rem     |
| Landing title           | 2.5rem   |
| Detail headword         | 1.1rem   |
| Inputs, buttons         | 1rem     |
| Secondary text, lists   | 0.9rem   |
| Legend, links           | 0.85rem  |
| Node labels, field tags | 0.75rem  |
| Edge labels             | 0.625rem |

Parts of speech are italic.

## 4. The tree

### Nodes

- A rounded box (`rx` 6), 32 px tall and at least 120 px wide. The label reads
  `headword (lang)`, and the box widens to fit it at about 7 px per character.
  Labels never truncate.
- Default: `--bg-2` fill, 1 px `--ui-border` stroke, `--tx` text.
- Focus node: `--focus` fill and stroke, `--bg` text.
- Redlink node (no Wiktionary entry): 2 px `--danger` stroke.
- "+N more" marker: same box, no fill, dashed stroke (`4 3`), `--tx-2` text. It
  sits after its siblings.
- Ancestors and descendants share one style; only position tells them apart.

### Edges

- Every relation draws the same line: 1.5 px `--tx-2`, solid, with one filled
  arrowhead at the descendant end. The line stops at the child's border so the
  arrowhead stays visible.
- Each edge is a horizontal S-curve. Its control points lean toward the other end,
  so the arrowhead follows the curve's real direction.
- A parent's outgoing edges leave from ports spread across the middle 60% of its
  right border, ordered by the children's y so they don't cross.
- The relation shows as a pill label at the curve's midpoint: `--bg` fill, 1 px
  `--tx-3` border, `--tx-2` text, and a 2 px `--bg` halo. Its abbreviation
  (`inh.`, `bor.`, `der.`, ...) has the full name as a tooltip.
- Borrowings and calques get a `--rel-borrowing` label border. Mentions would
  get `--rel-weak`, but tree walks exclude mention edges, so it does not show
  today. Every other relation stays neutral, since most edges are ordinary
  inheritance or derivation.

### Spacing

| Measure        | Value                                                 |
| -------------- | ----------------------------------------------------- |
| Column gap     | 64 px between generations (room for the curves)       |
| Sibling gap    | 16 px between node boxes, doubled between cousins     |
| Column width   | the widest node in that generation                    |
| Children shown | 10 per parent before "+N more"                        |
| Viewbox padding| 16 px                                                 |

Siblings sort in a fixed order: morphemes in word order, then the rest
alphabetically, then the "+N more" marker.

### Legend

A popover from the circled "i" button, anchored bottom left. It explains the
link line and the "+N more" box. It does not yet cover the label colors, the
focus node, or redlinks.

## 5. Screen layout

There are no breakpoints. The canvas fills the viewport, and every control
floats above it.

| Element          | Position              | Notes                      |
| ---------------- | --------------------- | -------------------------- |
| Search bar       | top center            | wraps on narrow screens    |
| Detail card      | top right             | max width 16rem            |
| Legend           | bottom left           | popover                    |
| Not-found pill   | top center, below bar | `--danger` text and border |
| Homograph picker | top center, below bar | one button per section     |
| Badges           | bottom right, fixed   | version and GitHub link    |

The search bar holds, in order: the legend button, the headword field, the
language combobox, the search and random buttons, a "Keep lang code" checkbox,
and the theme toggle. The canvas reserves 9rem at the top for the docked bar.

The landing page shows a centered card (title, author line, two lead paragraphs,
and the search controls) over a blurred, inert preview of the "etymology" tree.
Submitting the card animates it into the docked search bar over 350 ms before
navigating.

The error page shows the status code and message, centered, with the badges and
no other chrome.

## 6. Interaction

- Single click on a node shows its details in the detail card, after a 300 ms
  delay so a double click can cancel it.
- Double click on a node opens that word's tree. The focus node ignores it.
- Enter or Space on a focused node acts like a single click. On a "+N more"
  marker it expands the parent.
- Escape closes the homograph picker, or resets the detail card to the focus
  word.
- Pan and zoom use d3-zoom: drag to pan, wheel or pinch to zoom, from 0.5× to
  8×. Double-click zoom is off.
- The tree fits the screen on load and after every expansion. The fit stays
  between 0.5× and 2×. If 0.5× still doesn't fit, a toast tells the user to pan
  or zoom.
- A spinner appears only after 300 ms of loading, and a "Still loading..." toast
  after 1,200 ms, so fast requests show nothing.
- A rate-limited request shows a warning toast. Other failed requests show an
  error toast with the server's message.

## 7. Accessibility

What exists:

- Nodes and "+N more" markers are focusable `role="button"` elements.
- Icon buttons carry `aria-label` and `title`. Decorative SVGs are
  `aria-hidden`.
- Fields have real `<label>` elements. The spinner is `role="status"` and the
  not-found message is `role="alert"`.
- The landing preview tree is `inert` and `aria-hidden`.

Known gaps, for the reskin to address:

- No custom focus styles; the UI relies on browser defaults.
- No `prefers-reduced-motion` handling.
- No keyboard way to open another word's tree (the double-click action).
- No hover states on nodes or edges.

## 8. Verifying UI changes

Drive the UI through the Playwright harness in `web/e2e/` (`npm run test:e2e`),
and keep any interaction worth checking as a spec. Query elements with
`getByRole` and `getByLabel`, so a spec fails when accessibility semantics
regress. `web/e2e/README.md` covers the hydration quirk on `/`.
