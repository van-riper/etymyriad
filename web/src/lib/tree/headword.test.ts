import { describe, expect, it } from 'vitest';
import { displayHeadword } from './headword';

describe('displayHeadword', () => {
  it('prefixes a reconstructed headword with an asterisk', () => {
    expect(displayHeadword('kreup-', true)).toBe('*kreup-');
  });

  it('leaves a non-reconstructed headword unchanged', () => {
    expect(displayHeadword('etymology', false)).toBe('etymology');
  });

  it('decodes Wiktionary unsupported-title escapes', () => {
    expect(displayHeadword('($··)/`tilde``tilde``tilde`', false)).toBe(
      '($··)/~~~',
    );
    expect(displayHeadword('m(`lowbar` `lowbar`)m', false)).toBe('m(_ _)m');
  });

  it('leaves an unknown backtick token alone', () => {
    expect(displayHeadword('`repl`', false)).toBe('`repl`');
  });
});
