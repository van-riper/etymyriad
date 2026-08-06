import type { ViewBox } from './treeLayout';

// Below this scale, node labels stop being legible (ETYM-126). A tree
// too large to fit the viewport at this floor starts partly off-screen
// instead of shrinking further -- pan/zoom reaches the rest.
export const FLOOR_SCALE = 0.5;

// Above this scale, nodes and labels render oversized relative to
// their native NODE_WIDTH/NODE_HEIGHT (treeLayout.ts) -- a tree too
// small to fill the viewport at this ceiling leaves margin around it
// instead of growing further, so node size stays comparable across
// trees of very different sizes rather than scaling with how tiny the
// viewBox happens to be. Deliberately much lower than the zoom
// gesture's own max scale (TreeDiagram.svelte's scaleExtent) -- that
// bound is for a user zooming in by hand, not the initial fit.
export const CEILING_SCALE = 2;

export interface ZoomTransform {
  x: number;
  y: number;
  k: number;
}

export function computeFitTransform(
  viewBox: ViewBox,
  containerWidth: number,
  containerHeight: number,
): ZoomTransform {
  const k = Math.min(
    CEILING_SCALE,
    Math.max(
      FLOOR_SCALE,
      Math.min(containerWidth / viewBox.width, containerHeight / viewBox.height),
    ),
  );
  const centerX = viewBox.minX + viewBox.width / 2;
  const centerY = viewBox.minY + viewBox.height / 2;
  return {
    k,
    x: containerWidth / 2 - k * centerX,
    y: containerHeight / 2 - k * centerY,
  };
}
