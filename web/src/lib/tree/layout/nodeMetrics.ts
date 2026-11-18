import { displayHeadword } from '../headword';
import type { TreeNode } from '../../shared/types';

export const NODE_WIDTH = 144;
export const MARKER_HEIGHT = 32;

// Matches TreeDiagram.svelte's `.node rect` stroke-width. A stroke
// straddles its path, so it adds this much to the rendered bounding
// box on top of the rect's own width/height: callers measuring a
// rendered node (e.g. via getBoundingClientRect) must account for it.
export const NODE_STROKE_WIDTH = 1;

// Each card metric below must match TreeDiagram.svelte's `.card` rules.
const CARD_PADDING_X = 8;
const CARD_PADDING_Y = 6;
const CARD_CONTENT_WIDTH = NODE_WIDTH - 2 * CARD_PADDING_X;
const GLOSS_MAX_LINES = 2;

interface CardRow {
  lineHeight: number;
  // 0.6em: wider than Inter's average glyph in Latin, Greek or
  // Cyrillic, so an estimate errs toward a taller card, not clipping.
  charWidth: number;
}

const LANG_NAME_ROW: CardRow = { lineHeight: 12, charWidth: 6 };
const HEADWORD_ROW: CardRow = { lineHeight: 18, charWidth: 9 };
const GLOSS_ROW: CardRow = { lineHeight: 14, charWidth: 6.6 };

export function composeLabel(node: TreeNode): string {
  return `${displayHeadword(node.headword, node.isReconstructed)} (${node.langCode})`;
}

// Greedy word wrap, breaking a word only when it can't fit a line of
// its own, as CSS `overflow-wrap: anywhere` does.
export function estimateLineCount(text: string, charsPerLine: number): number {
  let lines = 1;
  let used = 0;
  for (const word of text.split(/\s+/).filter(Boolean)) {
    const length = [...word].length;
    const needed = used === 0 ? length : used + 1 + length;
    if (needed <= charsPerLine) {
      used = needed;
      continue;
    }
    if (used > 0) lines += 1;
    const wordLines = Math.ceil(length / charsPerLine);
    lines += wordLines - 1;
    used = length - (wordLines - 1) * charsPerLine;
  }
  return lines;
}

function rowHeight(text: string, row: CardRow, maxLines = Infinity): number {
  const charsPerLine = Math.floor(CARD_CONTENT_WIDTH / row.charWidth);
  const lines = Math.min(maxLines, estimateLineCount(text, charsPerLine));
  return lines * row.lineHeight;
}

// shortcut: estimates wrapping from character counts instead of
// measuring rendered text, so a run of unusually wide glyphs can
// overflow its card; measure via canvas once that shows up in QA.
export function cardHeight(
  node: Pick<TreeNode, 'langName' | 'headword' | 'isReconstructed' | 'gloss'>,
): number {
  const headword = displayHeadword(node.headword, node.isReconstructed);
  return (
    2 * CARD_PADDING_Y +
    rowHeight(node.langName, LANG_NAME_ROW) +
    rowHeight(headword, HEADWORD_ROW) +
    (node.gloss ? rowHeight(node.gloss, GLOSS_ROW, GLOSS_MAX_LINES) : 0)
  );
}
