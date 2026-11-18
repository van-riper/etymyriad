import { describe, expect, it } from 'vitest';
import { cardHeight } from './index';
import { estimateLineCount } from './nodeMetrics';

const shortCard = {
  langName: 'English',
  headword: 'father',
  isReconstructed: false,
  gloss: null,
};

describe('cardHeight', () => {
  it('gives every one-line card with no gloss the same height', () => {
    expect(cardHeight(shortCard)).toBe(
      cardHeight({ ...shortCard, headword: 'or' }),
    );
  });

  it('grows a card whose headword wraps past one line', () => {
    expect(
      cardHeight({
        ...shortCard,
        headword: 'превысокомногорассмотрительствующий',
      }),
    ).toBeGreaterThan(cardHeight(shortCard));
  });

  it('counts the asterisk a reconstructed headword renders with', () => {
    const headword = 'a'.repeat(14);
    expect(
      cardHeight({ ...shortCard, headword, isReconstructed: true }),
    ).toBeGreaterThan(cardHeight({ ...shortCard, headword }));
  });

  it('grows a card whose language name wraps past one line', () => {
    expect(
      cardHeight({
        ...shortCard,
        langName: 'Proto-Central-Eastern Malayo-Polynesian',
      }),
    ).toBeGreaterThan(cardHeight(shortCard));
  });

  it('adds a gloss row only when there is a gloss', () => {
    expect(
      cardHeight({ ...shortCard, gloss: 'a male parent' }),
    ).toBeGreaterThan(cardHeight(shortCard));
  });

  it('caps the gloss row at two lines', () => {
    const twoLines = cardHeight({ ...shortCard, gloss: 'word '.repeat(8) });
    const manyLines = cardHeight({ ...shortCard, gloss: 'word '.repeat(80) });
    expect(manyLines).toBe(twoLines);
    expect(twoLines).toBeGreaterThan(
      cardHeight({ ...shortCard, gloss: 'word' }),
    );
  });
});

describe('estimateLineCount', () => {
  it('fits a short text on one line', () => {
    expect(estimateLineCount('aa bb', 5)).toBe(1);
  });

  it('moves a word that does not fit to the next line', () => {
    expect(estimateLineCount('aaaa bbbb', 5)).toBe(2);
  });

  it('breaks a word longer than a line anywhere', () => {
    expect(estimateLineCount('a'.repeat(12), 5)).toBe(3);
  });

  it('starts a long word on a fresh line before breaking it', () => {
    expect(estimateLineCount(`aaaa ${'b'.repeat(12)}`, 5)).toBe(4);
  });

  it('counts code points, not UTF-16 units', () => {
    expect(estimateLineCount('𐌰𐌱𐌲𐌳𐌴', 5)).toBe(1);
  });
});
