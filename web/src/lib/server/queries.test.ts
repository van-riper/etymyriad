import { describe, expect, it, vi } from 'vitest';
import {
  languageList,
  randomTerm,
  termDetail,
  termsByHeadword,
  treeExpand,
  treeSlice,
} from './queries';
import { getSql } from './db';
import { MAX_SIBLINGS_PER_PARENT } from '../tree/layout';
import type { TreeSlice } from '$lib/shared/types';

type Sql = Awaited<ReturnType<typeof getSql>>;

const FIXTURE_LANG = 'zzz-test';

async function removeFixtureLanguage(sql: Sql, code: string): Promise<void> {
  const terms = sql`SELECT t.id FROM term t JOIN language l
    ON l.id = t.language_id WHERE l.code = ${code}`;
  await sql`DELETE FROM pickable_term WHERE term_id IN (${terms})`;
  await sql`DELETE FROM edge WHERE src_term_id IN (${terms})
    OR dst_term_id IN (${terms})`;
  await sql`DELETE FROM sense WHERE term_id IN (${terms})`;
  await sql`DELETE FROM term WHERE id IN (${terms})`;
  await sql`DELETE FROM language WHERE code = ${code}`;
}

// Clears stale rows first, runs the test body, and always removes the
// fixture language, even when an assertion throws.
async function withLanguage(
  code: string,
  body: (sql: Sql, languageId: number) => Promise<void>,
): Promise<void> {
  const sql = await getSql();
  await removeFixtureLanguage(sql, code);
  try {
    const [{ id }] = (await sql`
      INSERT INTO language (code, name, kind)
      VALUES (${code}, 'Test', 'regular') RETURNING id`) as Array<{
      id: number;
    }>;
    await body(sql, id);
  } finally {
    await removeFixtureLanguage(sql, code);
  }
}

async function withBankFixture(
  body: (sql: Sql, id: (headword: string) => number) => Promise<void>,
): Promise<void> {
  await withLanguage(FIXTURE_LANG, async (sql, langId) => {
    const terms = (await sql`
      INSERT INTO term (language_id, headword)
      VALUES (${langId}, 'bank'), (${langId}, 'river'), (${langId}, 'money')
      RETURNING id, headword`) as Array<{ id: number; headword: string }>;
    const id = (w: string) => terms.find((t) => t.headword === w)!.id;
    await sql`
      INSERT INTO sense (term_id, section, part_of_speech, gloss) VALUES
        (${id('bank')}, 1, 'noun', 'a slope'),
        (${id('bank')}, 2, 'noun', 'an institution'),
        (${id('river')}, 0, 'noun', 'water'),
        (${id('money')}, 0, 'noun', 'cash')`;
    await sql`
      INSERT INTO edge
        (src_term_id, dst_term_id, dst_section, rel_type, anchor)
      VALUES
        (${id('river')}, ${id('bank')}, 1, 'derived',
         'etymology_templates:0:der'),
        (${id('money')}, ${id('bank')}, 2, 'borrowed',
         'etymology_templates:0:bor')`;
    await sql`
      INSERT INTO pickable_term (term_id, language_id)
      SELECT id, ${langId} FROM term WHERE language_id = ${langId}`;
    await body(sql, id);
  });
}

async function insertTerm(
  sql: Sql,
  langId: number,
  headword: string,
): Promise<number> {
  const [{ id }] = (await sql`
    INSERT INTO term (language_id, headword)
    VALUES (${langId}, ${headword}) RETURNING id`) as Array<{ id: number }>;
  return id;
}

async function insertChain(
  sql: Sql,
  langId: number,
  length: number,
): Promise<number[]> {
  const ids: number[] = [];
  for (let i = 0; i < length; i++) {
    ids.push(await insertTerm(sql, langId, 'link' + i));
  }
  // ids[0] is the oldest ancestor, ids[length - 1] the newest descendant.
  for (let i = 0; i < ids.length - 1; i++) {
    await sql`
      INSERT INTO edge (src_term_id, dst_term_id, rel_type, anchor)
      VALUES (${ids[i]}, ${ids[i + 1]}, 'inherited', 'test')`;
  }
  return ids;
}

async function idFor(langCode: string, headword: string): Promise<number> {
  const sql = await getSql();
  const [row] = (await sql`
    SELECT t.id FROM term t JOIN language l ON l.id = t.language_id
    WHERE l.code = ${langCode} AND t.headword = ${headword}`) as Array<{
    id: number;
  }>;
  expect(row).toBeDefined();
  return row.id;
}

describe('section handling', () => {
  it('walkAncestors filters the first hop by section', async () => {
    await withBankFixture(async (_sql, id) => {
      const one = await treeSlice(id('bank'), 1);
      const two = await treeSlice(id('bank'), 2);
      const all = await treeSlice(id('bank'), 0);
      const heads = (s: TreeSlice | null) =>
        s!.nodes.map((n) => n.headword).sort();
      expect(heads(one)).toEqual(['bank', 'river']);
      expect(heads(two)).toEqual(['bank', 'money']);
      expect(heads(all)).toEqual(['bank', 'money', 'river']);
    });
  });

  it('lists one summary per section for a homograph', async () => {
    await withBankFixture(async (_sql, id) => {
      expect(await termsByHeadword(FIXTURE_LANG, 'bank')).toEqual([
        { id: id('bank'), section: 1, partOfSpeech: 'noun', gloss: 'a slope' },
        {
          id: id('bank'),
          section: 2,
          partOfSpeech: 'noun',
          gloss: 'an institution',
        },
      ]);
      expect(await termsByHeadword(FIXTURE_LANG, 'bank', 2)).toHaveLength(1);
      expect(await termsByHeadword(FIXTURE_LANG, 'bank', 7)).toEqual([]);
    });
  });

  it('returns a section 0 summary for a redlink term', async () => {
    await withLanguage(FIXTURE_LANG, async (sql, langId) => {
      const id = await insertTerm(sql, langId, 'ghost');
      expect(await termsByHeadword(FIXTURE_LANG, 'ghost')).toEqual([
        { id, section: 0, partOfSpeech: null, gloss: null },
      ]);
    });
  });

  it('summarizes a section by its glossed sense', async () => {
    await withLanguage(FIXTURE_LANG, async (sql, langId) => {
      const id = await insertTerm(sql, langId, 'mixed');
      await sql`
        INSERT INTO sense (term_id, section, part_of_speech, gloss) VALUES
          (${id}, 1, 'noun', NULL),
          (${id}, 1, 'noun', 'has a gloss')`;
      expect(await termsByHeadword(FIXTURE_LANG, 'mixed')).toEqual([
        { id, section: 1, partOfSpeech: 'noun', gloss: 'has a gloss' },
      ]);
    });
  });

  it('returns no summaries for an unknown headword', async () => {
    expect(await termsByHeadword('en', 'zzznotaword')).toEqual([]);
  });
});

describe('citations', () => {
  it('derives citations from the dataset date', async () => {
    await withBankFixture(async (sql, id) => {
      const [{ dump_date }] = (await sql`
        SELECT to_char(dump_date, 'YYYY-MM-DD') AS dump_date
        FROM dataset`) as Array<{ dump_date: string }>;
      const slice = await treeSlice(id('bank'), 1);
      expect(slice!.edges[0].sourceRef).toBe(
        `wiktionary:${dump_date}:zzz-test:bank#etymology_templates:0:der`,
      );
      const detail = await termDetail(id('river'));
      expect(detail!.sourceRef).toBe(`wiktionary:${dump_date}:zzz-test:river`);
      expect(detail!.isRedlink).toBe(false);
    });
  });
});

describe('randomTerm', () => {
  it('returns a real pair from the table', async () => {
    expect(await randomTerm()).not.toBeNull();
  });

  it('restricts the pick to the given language code', async () => {
    const pick = await randomTerm('en');
    expect(pick!.langCode).toBe('en');
  });

  it('always finds a term, even at the top of the range', async () => {
    await withBankFixture(async () => {
      const spy = vi.spyOn(Math, 'random');
      try {
        const cases: Array<[number, string]> = [
          [0, 'bank'],
          [0.9999999, 'money'],
        ];
        for (const [value, headword] of cases) {
          spy.mockReturnValueOnce(value);
          const pick = await randomTerm(FIXTURE_LANG);
          expect(pick).toEqual({ langCode: FIXTURE_LANG, headword });
        }
        spy.mockReturnValueOnce(0.5);
        expect((await randomTerm(FIXTURE_LANG))?.langCode).toBe(FIXTURE_LANG);
      } finally {
        spy.mockRestore();
      }
    });
  });

  it('returns null for a language with no pickable term', async () => {
    expect(await randomTerm('zzznotalang')).toBeNull();
  });
});

describe('languageList', () => {
  it('only lists languages with a pickable term', async () => {
    await withLanguage('zzz-nopick', async () => {
      const languages = await languageList();
      expect(languages.some((l) => l.code === 'en')).toBe(true);
      expect(languages.some((l) => l.code === 'zzz-nopick')).toBe(false);
    });
  });
});

describe('termDetail', () => {
  it('fetches a term with its senses by id', async () => {
    const detail = await termDetail(await idFor('en', 'etymology'));

    expect(detail!.headword).toBe('etymology');
    expect(detail!.langCode).toBe('en');
    expect(detail!.langName).toBe('English');
    expect(detail!.senses.length).toBeGreaterThan(0);
    expect(detail!.isRedlink).toBe(false);
  });

  it('flags a term with no senses as a redlink', async () => {
    await withLanguage(FIXTURE_LANG, async (sql, langId) => {
      const id = await insertTerm(sql, langId, 'ghost');
      const detail = await termDetail(id);
      expect(detail!.isRedlink).toBe(true);
      expect(detail!.senses).toEqual([]);
    });
  });

  it('returns null for an id that does not exist', async () => {
    expect(await termDetail(-1)).toBeNull();
  });
});

describe('treeSlice', () => {
  it('tags the focus word at depth 0', async () => {
    const focusId = await idFor('la', 'etymologia');
    const tree = await treeSlice(focusId, 0);

    expect(tree!.nodes.find((n) => n.id === focusId)?.depth).toBe(0);
  });

  it('walks the en "etymology" backtrace to la and grc', async () => {
    const focusId = await idFor('en', 'etymology');
    const tree = await treeSlice(focusId, 0);

    const ancestors = tree!.nodes.filter((n) => n.depth < 0);
    expect(ancestors.some((n) => n.langCode === 'la')).toBe(true);
    expect(ancestors.some((n) => n.langCode === 'grc')).toBe(true);
    expect(
      tree!.edges.every((e) => e.sourceRef.startsWith('wiktionary:')),
    ).toBe(true);
  });

  it('walks ancestors an arbitrary number of hops', async () => {
    await withLanguage('zzz-longchain', async (sql, langId) => {
      const ids = await insertChain(sql, langId, 4);
      const tree = await treeSlice(ids[3], 0);
      expect(Math.min(...tree!.nodes.map((n) => n.depth))).toBe(-3);
    });
  });

  it('walks descendants an arbitrary number of hops', async () => {
    await withLanguage('zzz-longchain', async (sql, langId) => {
      const ids = await insertChain(sql, langId, 4);
      const tree = await treeSlice(ids[0], 0);
      expect(Math.max(...tree!.nodes.map((n) => n.depth))).toBe(3);
    });
  });

  it('counts a child cited from several sections once', async () => {
    await withLanguage(FIXTURE_LANG, async (sql, langId) => {
      const focusId = await insertTerm(sql, langId, 'focus');
      const parentIds: number[] = [];
      for (let i = 0; i <= MAX_SIBLINGS_PER_PARENT; i++) {
        parentIds.push(await insertTerm(sql, langId, 'parent' + i));
      }
      for (const parentId of parentIds) {
        await sql`
          INSERT INTO edge (src_term_id, dst_term_id, rel_type, anchor)
          VALUES (${parentId}, ${focusId}, 'derived', 'test')`;
      }
      await sql`
        INSERT INTO edge
          (src_term_id, dst_term_id, dst_section, rel_type, anchor)
        VALUES (${parentIds[0]}, ${focusId}, 1, 'derived', 'test'),
               (${parentIds[0]}, ${focusId}, 2, 'derived', 'test')`;

      const tree = await treeSlice(focusId, 0);
      expect(tree!.nodes.filter((n) => n.depth === -1)).toHaveLength(
        MAX_SIBLINGS_PER_PARENT,
      );
      expect(tree!.overflow).toEqual([
        { parentId: focusId, direction: 'ancestor', count: 1 },
      ]);
    });
  });

  it('terminates on a cyclic chain instead of recursing forever', async () => {
    await withLanguage('zzz-cycle', async (sql, langId) => {
      const xId = await insertTerm(sql, langId, 'cyclex');
      const yId = await insertTerm(sql, langId, 'cycley');
      await sql`
        INSERT INTO edge (src_term_id, dst_term_id, rel_type, anchor)
        VALUES (${xId}, ${yId}, 'inherited', 'test'),
               (${yId}, ${xId}, 'inherited', 'test')`;

      const tree = await treeSlice(xId, 0);
      expect(tree!.nodes.some((n) => n.id === yId)).toBe(true);
    });
  });

  it('includes a surface_analysis ancestor edge', async () => {
    const focusId = await idFor('en', 'homological');
    const tree = await treeSlice(focusId, 0);

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
    expect(await treeSlice(-1, 0)).toBeNull();
  });

  it('excludes a mention-only edge from traversal', async () => {
    const focusId = await idFor('la', 'cognosco');
    await withLanguage('zzz-mention', async (sql, langId) => {
      const mentionId = await insertTerm(sql, langId, 'mentionword');
      await sql`
        INSERT INTO edge (src_term_id, dst_term_id, rel_type, anchor)
        VALUES (${mentionId}, ${focusId}, 'mention', 'test')`;

      const tree = await treeSlice(focusId, 0);
      expect(tree!.nodes.some((n) => n.id === mentionId)).toBe(false);
    });
  });

  it('tags a reconstructed focus node as such', async () => {
    const focusId = await idFor('ine-pro', 'kreup-');
    const tree = await treeSlice(focusId, 0);
    expect(tree!.nodes.find((n) => n.id === focusId)?.isReconstructed).toBe(
      true,
    );
  });

  it('tags a redlink ancestor and leaves the focus untagged', async () => {
    const focusId = await idFor('la', 'etymologia');
    await withLanguage('zzz-redlink', async (sql, langId) => {
      const redlinkId = await insertTerm(sql, langId, 'redlinkancestor');
      await sql`
        INSERT INTO edge (src_term_id, dst_term_id, rel_type, anchor)
        VALUES (${redlinkId}, ${focusId}, 'derived', 'test')`;

      const tree = await treeSlice(focusId, 0);
      expect(tree!.nodes.find((n) => n.id === redlinkId)?.isRedlink).toBe(true);
      expect(tree!.nodes.find((n) => n.id === focusId)?.isRedlink).toBe(false);
      expect(tree!.nodes.find((n) => n.id === focusId)?.isReconstructed).toBe(
        false,
      );
    });
  });

  it('caps a massive real fan-out and reports the overflow', async () => {
    const focusId = await idFor('en', '-ly');
    const tree = await treeSlice(focusId, 0);

    const kept = tree!.nodes.filter((n) => n.depth === 1);
    expect(kept.length).toBeGreaterThan(0);
    expect(kept.length).toBeLessThanOrEqual(MAX_SIBLINGS_PER_PARENT);

    const overflow = tree!.overflow?.find(
      (o) => o.parentId === focusId && o.direction === 'descendant',
    );
    expect(overflow).toBeDefined();
    expect(overflow!.count).toBeGreaterThan(15000);
  });

  it('keeps the most relevant children under a cap', async () => {
    const focusId = await idFor('en', '-ly');
    const tree = await treeSlice(focusId, 0);

    const keptIds = new Set(
      tree!.nodes.filter((n) => n.depth === 1).map((n) => n.id),
    );
    const keptRelTypes = tree!.edges
      .filter((e) => e.srcId === focusId && keptIds.has(e.dstId))
      .map((e) => e.relType);

    // '-ly' has exactly 2 'compound' edges, which outrank its 15k+
    // 'affix' edges. Both must survive the cap.
    expect(keptRelTypes.filter((r) => r === 'compound')).toHaveLength(2);
  });
});

describe('treeExpand', () => {
  it('fetches the next batch beyond an already-known set', async () => {
    const focusId = await idFor('en', '-ly');
    const tree = await treeSlice(focusId, 0);
    const knownIds = tree!.nodes.filter((n) => n.depth === 1).map((n) => n.id);

    const expansion = await treeExpand(focusId, 'descendant', 0, knownIds);

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
    const focusId = await idFor('la', 'negligo');
    const expansion = await treeExpand(focusId, 'descendant', 0, []);

    expect(
      expansion.overflow.find((o) => o.parentId === focusId),
    ).toBeUndefined();
  });

  it('expands ancestors an arbitrary number of hops', async () => {
    await withLanguage('zzz-longchain', async (sql, langId) => {
      const ids = await insertChain(sql, langId, 4);
      const expansion = await treeExpand(ids[3], 'ancestor', 0, []);
      expect(Math.min(...expansion.nodes.map((n) => n.depth))).toBe(-3);
    });
  });
});
