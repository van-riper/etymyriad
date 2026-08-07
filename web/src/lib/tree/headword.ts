// Reconstructed forms use the standard linguistic asterisk convention
// (e.g. *leg-), per is_reconstructed in db/schema.sql.
export function displayHeadword(
  headword: string,
  isReconstructed: boolean,
): string {
  return isReconstructed ? `*${headword}` : headword;
}
