# Roadmap to v1

This is a draft. Every criterion is a proposal until the owner accepts it.
The project board remains the source of truth for individual backlog items.

## Goal

A visitor can look up any word, see a sourced family tree, and check every
claim against Wiktionary. It works on a phone and loads fast.

## Acceptance criteria

### 1. Data

- Production serves the full dump (every language in the registry), not only
  the Indo-European subset.
- Every edge shows its Wiktionary anchor and the dump date.
- Golden tests pass. Known crosscheck gaps against Wiktionary's etymology
  trees are listed and accepted, not hidden.
- A reload to Neon runs from the ETL workflow with no manual steps.

### 2. Finding a word

- Typing a headword suggests matches with their language, and homographs can
  be told apart.
- Pasting a Wiktionary URL opens that word.
- A random-word button works, and the landing page opens on a good default
  tree.
- A word missing from the graph shows a clear not-found state. A live
  Wiktionary fallback is optional.

### 3. The tree

- Any word renders a bounded ancestor and descendant slice, laid out the same
  way every time.
- Nodes are readable without zooming, and the tree opens at 1:1 on the focus.
- Users can expand a branch.
- Relation types (borrowed, inherited, cognate) are visible, with a legend.

### 4. Word detail

- Selecting a node shows its senses and sources, with a link to Wiktionary.
- Gender, pronunciation, and paradigms are not required.

### 5. Quality bar

- Search, tap targets, pan, and zoom work on a phone.
- Keyboard navigation, visible focus, screen-reader labels, and reduced
  motion are supported.
- The first tree loads in about 2 seconds or less on a warm database. A cold
  Neon start is either handled or accepted.
- `npm run check`, the unit tests, and the data e2e specs pass in CI.

### 6. Ship

- The UI rewrite is done and `docs/DESIGN.md` describes the new UI.
- The site is live at etymyriad.com from a `v1.0.0` tag.
- The README explains the sourcing promise.

## Non-goals

- AI features
- Geography map
- Word of the Day
- Fuzzy "did you mean" search
- Live wikitext renderer for senses
- Lexeme-observed bug reports
- Adopting etymologyexplorer's design language sitewide

## Open risks

- The UI rewrite is the largest unknown and gates sections 2 to 5. Settle its
  scope before locking these criteria.
- Loading the full dump to Neon adds reload time on the small compute. Check
  query speed on the larger tables before committing to full coverage in
  production.
