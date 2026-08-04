import { describe, expect, it } from 'vitest';
import { treeUrl } from './treeUrl';

describe('treeUrl', () => {
  it('builds a path from lang and headword', () => {
    expect(treeUrl('en', 'etymology')).toBe('/tree/en/etymology');
  });

  it('encodes a headword containing a slash so it stays one segment', () => {
    const url = treeUrl('en', 'and/or');
    expect(url).toBe('/tree/en/and%2For');
    const [, , , headwordSegment] = url.split('/');
    expect(decodeURIComponent(headwordSegment)).toBe('and/or');
  });

  it('appends an etym query param when given', () => {
    expect(treeUrl('en', 'etymology', 'abc123')).toBe(
      '/tree/en/etymology?etym=abc123',
    );
  });

  it('omits the query string when etym is not given', () => {
    expect(treeUrl('en', 'etymology')).not.toContain('?');
  });
});
