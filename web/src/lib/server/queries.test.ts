import { describe, expect, it } from 'vitest';
import {
  randomLexeme,
  lexemeDetail,
  lexemesByHeadword,
  treeSlice,
} from './queries';
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

describe('lexemesByHeadword', () => {
  it('resolves a unique headword to a single-element array', async () => {
    const matches = await lexemesByHeadword('en', 'etymology');

    expect(matches).toHaveLength(1);
    expect(typeof matches[0].id).toBe('string');
  });

  it('returns one summary per homograph when ambiguous', async () => {
    const matches = await lexemesByHeadword('en', 'bank');

    expect(matches.length).toBeGreaterThan(1);
    expect(matches.every((m) => typeof m.etymKey === 'string')).toBe(true);
  });

  it('resolves one homograph when etymKey narrows it', async () => {
    const ambiguous = await lexemesByHeadword('en', 'bank');
    const target = ambiguous[0];

    const matches = await lexemesByHeadword('en', 'bank', target.etymKey);

    expect(matches).toEqual([target]);
  });

  it('returns an empty array for a headword that does not exist', async () => {
    const matches = await lexemesByHeadword('en', 'zzznotaword');
    expect(matches).toEqual([]);
  });
});

describe('treeSlice', () => {
  async function idFor(langCode: string, headword: string): Promise<string> {
    const sql = await getSql();
    const [row] = (await sql`
      SELECT id FROM lexeme
      WHERE lang_code = ${langCode} AND headword = ${headword}
      LIMIT 1
    `) as Array<{ id: string }>;
    expect(row).toBeDefined();
    return row.id;
  }

  it('tags the focus word at depth 0', async () => {
    const focusId = await idFor('la', 'etymologia');
    const tree = await treeSlice(focusId, 1);

    expect(tree).not.toBeNull();
    const focusNode = tree!.nodes.find((n) => n.id === focusId);
    expect(focusNode?.depth).toBe(0);
  });

  it('tags direct ancestors at depth -1, with source_ref', async () => {
    const focusId = await idFor('la', 'etymologia');
    const tree = await treeSlice(focusId, 1);

    const ancestor = tree!.nodes.find(
      (n) => n.langCode === 'grc' && n.headword === 'ἐτυμολογία',
    );
    expect(ancestor?.depth).toBe(-1);

    const edge = tree!.edges.find(
      (e) => e.srcId === ancestor!.id && e.dstId === focusId,
    );
    expect(edge).toBeDefined();
    expect(edge!.sourceRef).toBeTruthy();
  });

  it('tags direct descendants at depth 1, symmetrically', async () => {
    const focusId = await idFor('la', 'etymologia');
    const tree = await treeSlice(focusId, 1);

    const descendant = tree!.nodes.find(
      (n) => n.langCode === 'en' && n.headword === 'etymology',
    );
    expect(descendant?.depth).toBe(1);

    const edge = tree!.edges.find(
      (e) => e.srcId === focusId && e.dstId === descendant!.id,
    );
    expect(edge).toBeDefined();
  });

  it('walks multiple hops up to the depth cap', async () => {
    const focusId = await idFor('la', 'etymologia');
    const tree = await treeSlice(focusId, 2);

    const depths = tree!.nodes.map((n) => n.depth);
    expect(Math.min(...depths)).toBe(-2);
  });

  it('stops at the depth cap: no depth-2 nodes when maxDepth=1', async () => {
    const focusId = await idFor('la', 'etymologia');
    const tree = await treeSlice(focusId, 1);

    const depths = tree!.nodes.map((n) => n.depth);
    expect(Math.min(...depths)).toBe(-1);
    expect(Math.max(...depths)).toBe(1);
  });

  it('returns null for a focus id that does not exist', async () => {
    const tree = await treeSlice('00000000-0000-0000-0000-000000000000', 3);
    expect(tree).toBeNull();
  });

  it('tags a reconstructed focus node as such', async () => {
    const focusId = await idFor('ine-pro', 'kreup-');
    const tree = await treeSlice(focusId, 0);

    const focusNode = tree!.nodes.find((n) => n.id === focusId);
    expect(focusNode?.isReconstructed).toBe(true);
  });

  it('leaves a non-reconstructed node untagged', async () => {
    const focusId = await idFor('la', 'etymologia');
    const tree = await treeSlice(focusId, 0);

    const focusNode = tree!.nodes.find((n) => n.id === focusId);
    expect(focusNode?.isReconstructed).toBe(false);
  });
});
