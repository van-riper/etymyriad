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
      INSERT INTO lexeme (lang_code, headword, is_redlink, source_ref, degree)
      VALUES
        ('zzz-redlink', 'realword', false, 'test', 1),
        ('zzz-redlink', 'redlinkword', true, 'test', 1)
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
    const tree = await treeSlice(focusId);

    expect(tree).not.toBeNull();
    const focusNode = tree!.nodes.find((n) => n.id === focusId);
    expect(focusNode?.depth).toBe(0);
  });

  it('tags direct ancestors at depth -1, with source_ref', async () => {
    const focusId = await idFor('la', 'etymologia');
    const tree = await treeSlice(focusId);

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
    const tree = await treeSlice(focusId);

    const descendant = tree!.nodes.find(
      (n) => n.langCode === 'la' && n.headword === 'accognosco',
    );
    expect(descendant?.depth).toBe(1);

    const edge = tree!.edges.find(
      (e) => e.srcId === focusId && e.dstId === descendant!.id,
    );
    expect(edge).toBeDefined();
  });

  it('walks ancestors an arbitrary number of hops, with no depth limit', async () => {
    const sql = await getSql();
    await sql`
      INSERT INTO language (code, name) VALUES ('zzz-longchain', 'Longchain Test')
    `;
    const chainLength = 4;
    const ids: string[] = [];
    for (let i = 0; i < chainLength; i++) {
      const [{ id }] = (await sql`
        INSERT INTO lexeme (lang_code, headword, source_ref)
        VALUES ('zzz-longchain', ${'link' + i}, 'test')
        RETURNING id
      `) as Array<{ id: string }>;
      ids.push(id);
    }

    try {
      // ids[0] is the oldest ancestor, ids[chainLength - 1] the focus.
      for (let i = 0; i < ids.length - 1; i++) {
        await sql`
          INSERT INTO etymology (src_id, dst_id, rel_type, source_ref)
          VALUES (${ids[i]}, ${ids[i + 1]}, 'inherited', 'test')
        `;
      }

      const tree = await treeSlice(ids[ids.length - 1]);
      const depths = tree!.nodes.map((n) => n.depth);
      expect(Math.min(...depths)).toBe(-(chainLength - 1));
    } finally {
      await sql`DELETE FROM lexeme WHERE lang_code = 'zzz-longchain'`;
      await sql`DELETE FROM language WHERE code = 'zzz-longchain'`;
    }
  });

  it('walks descendants an arbitrary number of hops, with no depth limit', async () => {
    const sql = await getSql();
    await sql`
      INSERT INTO language (code, name) VALUES ('zzz-longchain', 'Longchain Test')
    `;
    const chainLength = 4;
    const ids: string[] = [];
    for (let i = 0; i < chainLength; i++) {
      const [{ id }] = (await sql`
        INSERT INTO lexeme (lang_code, headword, source_ref)
        VALUES ('zzz-longchain', ${'link' + i}, 'test')
        RETURNING id
      `) as Array<{ id: string }>;
      ids.push(id);
    }

    try {
      // ids[0] is the focus, ids[chainLength - 1] the most distant
      // descendant.
      for (let i = 0; i < ids.length - 1; i++) {
        await sql`
          INSERT INTO etymology (src_id, dst_id, rel_type, source_ref)
          VALUES (${ids[i]}, ${ids[i + 1]}, 'inherited', 'test')
        `;
      }

      const tree = await treeSlice(ids[0]);
      const depths = tree!.nodes.map((n) => n.depth);
      expect(Math.max(...depths)).toBe(chainLength - 1);
    } finally {
      await sql`DELETE FROM lexeme WHERE lang_code = 'zzz-longchain'`;
      await sql`DELETE FROM language WHERE code = 'zzz-longchain'`;
    }
  });

  it('terminates on a cyclic chain instead of recursing forever', async () => {
    // The real dataset has at least one genuine cycle: sa "कागद" and
    // its hi/mr/kok/mwr reflexes each cite the other as their source.
    // Without WALK_SAFETY_LIMIT, walking either direction here would
    // never terminate.
    const sql = await getSql();
    await sql`
      INSERT INTO language (code, name) VALUES ('zzz-cycle', 'Cycle Test')
    `;
    const [{ id: xId }] = (await sql`
      INSERT INTO lexeme (lang_code, headword, source_ref)
      VALUES ('zzz-cycle', 'cyclex', 'test')
      RETURNING id
    `) as Array<{ id: string }>;
    const [{ id: yId }] = (await sql`
      INSERT INTO lexeme (lang_code, headword, source_ref)
      VALUES ('zzz-cycle', 'cycley', 'test')
      RETURNING id
    `) as Array<{ id: string }>;

    try {
      await sql`
        INSERT INTO etymology (src_id, dst_id, rel_type, source_ref)
        VALUES
          (${xId}, ${yId}, 'inherited', 'test'),
          (${yId}, ${xId}, 'inherited', 'test')
      `;

      const tree = await treeSlice(xId);
      expect(tree).not.toBeNull();
      expect(tree!.nodes.some((n) => n.id === yId)).toBe(true);
    } finally {
      await sql`DELETE FROM lexeme WHERE lang_code = 'zzz-cycle'`;
      await sql`DELETE FROM language WHERE code = 'zzz-cycle'`;
    }
  });

  it('includes a surface_analysis ancestor edge (surf template)', async () => {
    // en "homological": {{der|en|grc|ὁμός}} + {{surf|en|homo-|logical}}.
    // rel_priority's VALUES list must carry every etym_rel_type, or a
    // JOIN against it silently drops that relation's edges entirely.
    const focusId = await idFor('en', 'homological');
    const tree = await treeSlice(focusId);

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
    const tree = await treeSlice('00000000-0000-0000-0000-000000000000');
    expect(tree).toBeNull();
  });

  it('excludes a mention-only edge from ancestor/descendant traversal', async () => {
    // ETYM-181: {{m+}} cites a same-page mention, not a derivation --
    // walking it directionally shows an attested reflex as if it were
    // its own proto-language root's ancestor.
    const sql = await getSql();
    const focusId = await idFor('la', 'cognōsco');
    await sql`
      INSERT INTO language (code, name) VALUES ('zzz-mention', 'Mention Test')
    `;
    const [{ id: mentionId }] = (await sql`
      INSERT INTO lexeme (lang_code, headword, source_ref)
      VALUES ('zzz-mention', 'mentionword', 'test')
      RETURNING id
    `) as Array<{ id: string }>;
    await sql`
      INSERT INTO etymology (src_id, dst_id, rel_type, source_ref)
      VALUES (${mentionId}, ${focusId}, 'mention', 'test')
    `;

    try {
      const tree = await treeSlice(focusId);
      expect(tree!.nodes.some((n) => n.id === mentionId)).toBe(false);
    } finally {
      await sql`DELETE FROM lexeme WHERE id = ${mentionId}`;
      await sql`DELETE FROM language WHERE code = 'zzz-mention'`;
    }
  });

  it('tags a reconstructed focus node as such', async () => {
    const focusId = await idFor('ine-pro', 'kreup-');
    const tree = await treeSlice(focusId);

    const focusNode = tree!.nodes.find((n) => n.id === focusId);
    expect(focusNode?.isReconstructed).toBe(true);
  });

  it('leaves a non-reconstructed node untagged', async () => {
    const focusId = await idFor('la', 'etymologia');
    const tree = await treeSlice(focusId);

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
      const tree = await treeSlice(focusId);
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
    const tree = await treeSlice(focusId);

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
    const tree = await treeSlice(focusId);

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
    const tree = await treeSlice(focusId);
    const knownIds = tree!.nodes.filter((n) => n.depth === 1).map((n) => n.id);

    const expansion = await treeExpand(focusId, 'descendant', 0, knownIds);

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
    const expansion = await treeExpand(focusId, 'descendant', 0, []);

    const overflow = expansion.overflow.find((o) => o.parentId === focusId);
    expect(overflow).toBeUndefined();
  });

  it('expands ancestors an arbitrary number of hops, with no depth limit', async () => {
    const sql = await getSql();
    await sql`
      INSERT INTO language (code, name) VALUES ('zzz-longchain', 'Longchain Test')
    `;
    const chainLength = 4;
    const ids: string[] = [];
    for (let i = 0; i < chainLength; i++) {
      const [{ id }] = (await sql`
        INSERT INTO lexeme (lang_code, headword, source_ref)
        VALUES ('zzz-longchain', ${'link' + i}, 'test')
        RETURNING id
      `) as Array<{ id: string }>;
      ids.push(id);
    }

    try {
      for (let i = 0; i < ids.length - 1; i++) {
        await sql`
          INSERT INTO etymology (src_id, dst_id, rel_type, source_ref)
          VALUES (${ids[i]}, ${ids[i + 1]}, 'inherited', 'test')
        `;
      }

      const focusId = ids[ids.length - 1];
      const expansion = await treeExpand(focusId, 'ancestor', 0, []);
      const depths = expansion.nodes.map((n) => n.depth);
      expect(Math.min(...depths)).toBe(-(chainLength - 1));
    } finally {
      await sql`DELETE FROM lexeme WHERE lang_code = 'zzz-longchain'`;
      await sql`DELETE FROM language WHERE code = 'zzz-longchain'`;
    }
  });
});
