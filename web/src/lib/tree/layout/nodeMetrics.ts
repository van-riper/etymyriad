import { displayHeadword } from '../headword';
import type { TreeNode } from '../../shared/types';

// The minimum/default node width: a node's rendered box never
// shrinks below this, even when its label is short enough to fit in
// less space (see widthForLabel below).
export const NODE_WIDTH = 120;
export const NODE_HEIGHT = 32;

// Matches TreeDiagram.svelte's `.node rect` stroke-width. A stroke
// straddles its path, so it adds this much to the rendered bounding
// box on top of the rect's own width/height: callers measuring a
// rendered node (e.g. via getBoundingClientRect) must account for it.
export const NODE_STROKE_WIDTH = 1;

// The rendered font is the page's body font-family (Inter, falling
// back to per-script Noto Sans faces for astral-plane headwords) at
// 0.75rem/12px (TreeDiagram.svelte's `.node text` rule sets no
// font-family of its own). 7px is calibrated against a real long
// non-Latin headword rendered in a browser (a Cyrillic label needed
// ~6.7px/char; plain Latin needs less), not just a Latin-only guess:
// the dataset's Indo-European scope spans several scripts (Cyrillic,
// Greek, diacritic-heavy reconstructed Latin, etc.), not only Latin.
// Re-verified against Inter (e2e/long-headword.spec.ts) after ETYM-42
// swapped the page font from the unstyled system-ui default.
// ponytail: naive per-character average, not a real glyph
// measurement, retune this constant, or measure for real via
// canvas/getBBox once available, if visual QA on another script shows
// systematic over/under-sizing.
const AVG_CHAR_WIDTH_PX = 7;

export function composeLabel(node: TreeNode): string {
  return `${displayHeadword(node.headword, node.isReconstructed)} (${node.langCode})`;
}

export function widthForLabel(label: string): number {
  return Math.max(NODE_WIDTH, Math.ceil(label.length * AVG_CHAR_WIDTH_PX));
}
