import { describe, expect, it } from 'vitest';
import { randomLexeme, lexemeDetail } from './queries';
import { getSql } from './db';

describe('randomLexeme', () => {
  it('returns a real lang_code/headword pair from the table', async () => {
    const pick = await randomLexeme();
    expect(pick).not.toBeNull();
  });

  it('restricts the pick to the given language code', async () => {
    const pick = await randomLexeme('en');

    expect(pick).not.toBeNull();
    expect(pick!.langCode).toBe('en');
  });

  it('returns null for a language code with no lexemes', async () => {
    const pick = await randomLexeme('zzznotalang');
    expect(pick).toBeNull();
  });
});

describe('lexemeDetail', () => {
  it('fetches a lexeme with its senses by id', async () => {
    const sql = await getSql();
    const [row] = (await sql`
      SELECT id FROM lexeme
      WHERE lang_code = 'en' AND headword = 'etymology'
      LIMIT 1
    `) as Array<{ id: string }>;
    expect(row).toBeDefined();

    const lexeme = await lexemeDetail(row.id);

    expect(lexeme).not.toBeNull();
    expect(lexeme!.headword).toBe('etymology');
    expect(lexeme!.langCode).toBe('en');
    expect(lexeme!.langName).toBe('English');
    expect(Array.isArray(lexeme!.senses)).toBe(true);
  });

  it('returns null for an id that does not exist', async () => {
    const lexeme = await lexemeDetail('00000000-0000-0000-0000-000000000000');
    expect(lexeme).toBeNull();
  });
});
