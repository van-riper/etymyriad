import { describe, expect, it } from 'vitest';
import {
  randomLexeme,
  lexemeDetail,
  lexemesByHeadword,
  treeSlice,
  treeExpand,
} from './queries';
import { getSql } from './db';
import { MAX_SIBLINGS_PER_PARENT } from '../tree/layout';

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

  it('never picks a redlink lexeme', async () => {
    const sql = await getSql();
    await sql`
      INSERT INTO language (code, name) VALUES ('zzz-redlink', 'Redlink Test')
    `;
    await sql`
      INSERT INTO lexeme (lang_code, headword, is_redlink, source_ref)
      VALUES
        ('zzz-redlink', 'realword', false, 'test'),
        ('zzz-redlink', 'redlinkword', true, 'test')
    `;

    try {
      for (let i = 0; i < 30; i++) {
        const pick = await randomLexeme('zzz-redlink');
        expect(pick?.headword).toBe('realword');
      }
    } finally {
      await sql`DELETE FROM lexeme WHERE lang_code = 'zzz-redlink'`;
      await sql`DELETE FROM language WHERE code = 'zzz-redlink'`;
    }
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
    expect(lexeme!.isRedlink).toBe(false);
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
    // Not 'etymologia' -> 'etymology': 'etymologia' has 30 real direct
    // descendants, and 'etymology''s 'derived' edge ranks behind the
    // 15 'borrowed'/'learned_borrowing' ones under the per-parent cap
    // (the same priority tiers the client-side cap already uses) --
    // 'cognōsco' has exactly one, well under the cap.
    const focusId = await idFor('la', 'cognōsco');
    const tree = await treeSlice(focusId, 1);

    const descendant = tree!.nodes.find(
      (n) => n.langCode === 'la' && n.headword === 'accognosco',
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

  it('includes a surface_analysis ancestor edge (surf template)', async () => {
    // en "homological": {{der|en|grc|ὁμός}} + {{surf|en|homo-|logical}}.
    // rel_priority's VALUES list must carry every etym_rel_type, or a
    // JOIN against it silently drops that relation's edges entirely.
    const focusId = await idFor('en', 'homological');
    const tree = await treeSlice(focusId, 1);

    const ancestorHeadwords = new Set(
      tree!.nodes.filter((n) => n.depth === -1).map((n) => n.headword),
    );
    expect(ancestorHeadwords).toContain('homo-');
    expect(ancestorHeadwords).toContain('logical');

    const surfEdges = tree!.edges.filter(
      (e) => e.dstId === focusId && e.relType === 'surface_analysis',
    );
    expect(surfEdges).toHaveLength(2);
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

  it('tags a redlink ancestor node as such', async () => {
    const sql = await getSql();
    const focusId = await idFor('la', 'etymologia');
    await sql`
      INSERT INTO language (code, name) VALUES ('zzz-redlink', 'Redlink Test')
    `;
    const [{ id: redlinkId }] = (await sql`
      INSERT INTO lexeme (lang_code, headword, is_redlink, source_ref)
      VALUES ('zzz-redlink', 'redlinkancestor', true, 'test')
      RETURNING id
    `) as Array<{ id: string }>;
    await sql`
      INSERT INTO etymology (src_id, dst_id, rel_type, source_ref)
      VALUES (${redlinkId}, ${focusId}, 'derived', 'test')
    `;

    try {
      const tree = await treeSlice(focusId, 1);
      const redlinkNode = tree!.nodes.find((n) => n.id === redlinkId);
      expect(redlinkNode?.isRedlink).toBe(true);

      const focusNode = tree!.nodes.find((n) => n.id === focusId);
      expect(focusNode?.isRedlink).toBe(false);
    } finally {
      await sql`DELETE FROM lexeme WHERE id = ${redlinkId}`;
      await sql`DELETE FROM language WHERE code = 'zzz-redlink'`;
    }
  });

  it('caps a massive real fan-out and reports the overflow', async () => {
    // English "-ly" has 15k+ direct descendants (every English -ly
    // adverb) -- the exact pathological case the per-parent cap
    // exists for.
    const focusId = await idFor('en', '-ly');
    const tree = await treeSlice(focusId, 5);

    const kept = tree!.nodes.filter((n) => n.depth === 1);
    expect(kept.length).toBeGreaterThan(0);
    expect(kept.length).toBeLessThanOrEqual(MAX_SIBLINGS_PER_PARENT);

    const overflow = tree!.overflow?.find(
      (o) => o.parentId === focusId && o.direction === 'descendant',
    );
    expect(overflow).toBeDefined();
    expect(overflow!.count).toBeGreaterThan(15000);
  });

  it('keeps the most etymologically relevant children under a cap', async () => {
    const focusId = await idFor('en', '-ly');
    const tree = await treeSlice(focusId, 5);

    const keptIds = new Set(
      tree!.nodes.filter((n) => n.depth === 1).map((n) => n.id),
    );
    const keptRelTypes = tree!.edges
      .filter((e) => e.srcId === focusId && keptIds.has(e.dstId))
      .map((e) => e.relType);

    // '-ly' has exactly 2 'compound' edges, which outrank its 15k+
    // 'affix' edges -- both must survive the cap.
    expect(keptRelTypes.filter((r) => r === 'compound')).toHaveLength(2);
  });
});

describe('treeExpand', () => {
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

  it('fetches the next batch beyond an already-known set, excluding it', async () => {
    const focusId = await idFor('en', '-ly');
    const tree = await treeSlice(focusId, 5);
    const knownIds = tree!.nodes.filter((n) => n.depth === 1).map((n) => n.id);

    const expansion = await treeExpand(focusId, 'descendant', 0, knownIds, 5);

    // Only the immediate next-batch of direct children is bounded by
    // the cap; the total node count can run higher if any of that
    // batch itself has its own (also capped) descendants.
    const directChildren = expansion.nodes.filter((n) => n.depth === 1);
    expect(directChildren.length).toBeGreaterThan(0);
    expect(directChildren.length).toBeLessThanOrEqual(MAX_SIBLINGS_PER_PARENT);
    for (const node of directChildren) {
      expect(knownIds).not.toContain(node.id);
    }

    const overflow = expansion.overflow.find(
      (o) => o.parentId === focusId && o.direction === 'descendant',
    );
    expect(overflow).toBeDefined();
    expect(overflow!.count).toBeGreaterThan(15000);
  });

  it('reports no overflow once a small fan-out is fully fetched', async () => {
    const focusId = await idFor('la', 'cognōsco');
    const expansion = await treeExpand(focusId, 'descendant', 0, [], 5);

    const overflow = expansion.overflow.find((o) => o.parentId === focusId);
    expect(overflow).toBeUndefined();
  });
});
