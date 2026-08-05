import type { ViewBox } from './treeLayout';

// Below this scale, node labels stop being legible (ETYM-126). A tree
// too large to fit the viewport at this floor starts partly off-screen
// instead of shrinking further -- pan/zoom reaches the rest.
export const FLOOR_SCALE = 0.5;

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
  const k = Math.max(
    FLOOR_SCALE,
    Math.min(containerWidth / viewBox.width, containerHeight / viewBox.height),
  );
  const centerX = viewBox.minX + viewBox.width / 2;
  const centerY = viewBox.minY + viewBox.height / 2;
  return {
    k,
    x: containerWidth / 2 - k * centerX,
    y: containerHeight / 2 - k * centerY,
  };
}
