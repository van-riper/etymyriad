import { describe, expect, it } from 'vitest';
import { randomLexeme, viewportTile } from './queries';
import { lexemePosition, lexemeDetail } from './queries';
import { getSql } from './db';

describe('lexemePosition', () => {
  it('returns id/x/y for a lexeme with a computed layout', async () => {
    const position = await lexemePosition('en', 'etymology');

    expect(position).not.toBeNull();
    expect(typeof position!.id).toBe('string');
    expect(typeof position!.x).toBe('number');
    expect(typeof position!.y).toBe('number');
  });

  it('returns null for a headword that does not exist', async () => {
    const position = await lexemePosition('en', 'zzznotaword');
    expect(position).toBeNull();
  });
});

describe('randomLexeme', () => {
  it('returns a real lang_code/headword pair from the table', async () => {
    const pick = await randomLexeme();

    expect(pick).not.toBeNull();
    const position = await lexemePosition(pick!.langCode, pick!.headword);
    expect(position).not.toBeNull();
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
    const position = await lexemePosition('en', 'etymology');
    const lexeme = await lexemeDetail(position!.id);

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

// A neighborhood box around a real point, sized relative to the
// graph's actual coordinate span rather than a fixed epsilon -- DrL's
// output scale isn't a documented constant, so a relative box avoids
// either missing everything (too small) or covering the whole graph
// (too large) regardless of what that scale turns out to be.
async function localBox(x: number, y: number) {
  const sql = await getSql();
  const [span] = (await sql`
    SELECT max(x) - min(x) AS span_x, max(y) - min(y) AS span_y
    FROM lexeme_layout
  `) as Array<{ span_x: number; span_y: number }>;
  const halfWidth = span.span_x / 500;
  const halfHeight = span.span_y / 500;
  return {
    minX: x - halfWidth,
    minY: y - halfHeight,
    maxX: x + halfWidth,
    maxY: y + halfHeight,
  };
}

describe('viewportTile', () => {
  it('returns only nodes within the requested bounding box', async () => {
    const sql = await getSql();
    const [sample] = (await sql`
      SELECT lexeme_id, x, y FROM lexeme_layout LIMIT 1
    `) as Array<{ lexeme_id: string; x: number; y: number }>;
    expect(sample).toBeDefined();

    const box = await localBox(sample.x, sample.y);
    const tile = await viewportTile(box);
    expect(tile.nodes.map((n) => n.id)).toContain(sample.lexeme_id);

    const [{ count: totalCount }] = (await sql`
      SELECT count(*)::int AS count FROM lexeme_layout
    `) as Array<{ count: number }>;
    expect(tile.nodes.length).toBeLessThan(totalCount);
  });

  it('excludes nodes below the requested minDegree', async () => {
    const sql = await getSql();
    const [low] = (await sql`
      SELECT lexeme_id, x, y, degree FROM lexeme_layout
      ORDER BY degree ASC LIMIT 1
    `) as Array<{
      lexeme_id: string;
      x: number;
      y: number;
      degree: number;
    }>;

    const box = await localBox(low.x, low.y);

    const withoutThreshold = await viewportTile(box);
    expect(withoutThreshold.nodes.map((n) => n.id)).toContain(low.lexeme_id);

    const withThreshold = await viewportTile(box, low.degree + 1);
    expect(withThreshold.nodes.map((n) => n.id)).not.toContain(low.lexeme_id);
  });

  it('uses the spatial index rather than a sequential scan', async () => {
    const sql = await getSql();
    const [sample] = (await sql`
      SELECT x, y FROM lexeme_layout LIMIT 1
    `) as Array<{ x: number; y: number }>;
    const box = await localBox(sample.x, sample.y);
    const centerX = (box.minX + box.maxX) / 2;
    const centerY = (box.minY + box.maxY) / 2;

    // Mirrors viewportTile's actual query -- keep these in sync.
    const plan = (await sql`
      EXPLAIN SELECT lexeme_id, x, y, degree FROM lexeme_layout
      WHERE pos <@ box(
        point(${box.minX}, ${box.minY}), point(${box.maxX}, ${box.maxY})
      ) AND degree >= 0
      ORDER BY pos <-> point(${centerX}, ${centerY})
      LIMIT 500
    `) as Array<{ 'QUERY PLAN': string }>;
    const planText = plan.map((row) => row['QUERY PLAN']).join('\n');

    expect(planText).toMatch(/lexeme_layout_pos_idx/);
    expect(planText).toMatch(/Index Scan/);
    expect(planText).not.toMatch(/Seq Scan on lexeme_layout/);
  });

  it('caps node count and always includes the box-center node', async () => {
    const sql = await getSql();
    const [hub] = (await sql`
      SELECT lexeme_id, x, y FROM lexeme_layout
      ORDER BY degree DESC LIMIT 1
    `) as Array<{ lexeme_id: string; x: number; y: number }>;

    // A box centered exactly on the highest-degree node in the dataset,
    // wide enough that real data density guarantees far more than the
    // cap of 5 nodes inside it (see ETYM-71's viewport-size bug).
    const box = {
      minX: hub.x - 50,
      minY: hub.y - 50,
      maxX: hub.x + 50,
      maxY: hub.y + 50,
    };

    const tile = await viewportTile(box, 0, 5);
    expect(tile.nodes.length).toBeLessThanOrEqual(5);
    expect(tile.nodes.map((n) => n.id)).toContain(hub.lexeme_id);
  });
});
