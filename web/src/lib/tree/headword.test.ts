import { describe, expect, it } from 'vitest';
import { displayHeadword } from './headword';

describe('displayHeadword', () => {
  it('prefixes a reconstructed headword with an asterisk', () => {
    expect(displayHeadword('kreup-', true)).toBe('*kreup-');
  });

  it('leaves a non-reconstructed headword unchanged', () => {
    expect(displayHeadword('etymology', false)).toBe('etymology');
  });
});
