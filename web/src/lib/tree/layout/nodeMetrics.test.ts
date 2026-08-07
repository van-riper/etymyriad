import { describe, expect, it } from 'vitest';
import { widthForLabel, NODE_WIDTH } from './index';

describe('widthForLabel', () => {
  it('floors short labels at NODE_WIDTH', () => {
    expect(widthForLabel('short')).toBe(NODE_WIDTH);
  });

  it('grows past the floor for a label longer than the floor fits', () => {
    expect(widthForLabel('a'.repeat(30))).toBe(210);
  });
});
