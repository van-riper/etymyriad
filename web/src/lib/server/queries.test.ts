import { describe, expect, it } from 'vitest';
import { egoNetwork } from './queries';

// Exercises the real local Postgres load (no mocks), matching the ETL's
// verified backtrace: water (en) -> watōr (gem-pro) -> wódr̥ (ine-pro).
//
// EXPECTED RED as of the etymology_number/sense migration: the local
// database still holds the old load (gloss/pos on lexeme, no sense
// table), so egoNetwork's new columns don't exist there yet. These
// assertions describe the query's correct behavior post-reload; they
// stay red until that reload happens, which is out of scope here.
describe('egoNetwork', () => {
  it('finds the real water -> watōr -> wódr̥ chain', async () => {
    const network = await egoNetwork('en', 'water', 3);

    expect(network).not.toBeNull();
    const headwords = network!.nodes.map((n) => n.headword);
    expect(headwords).toContain('water');
    expect(headwords).toContain('watōr');
    expect(headwords).toContain('wódr̥');
  });

  it('returns null for a headword that does not exist', async () => {
    const network = await egoNetwork('en', 'zzznotaword', 2);
    expect(network).toBeNull();
  });
});
