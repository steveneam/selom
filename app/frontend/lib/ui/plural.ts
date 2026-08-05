/**
 * Count + noun, agreeing in number — `1 row`, `2 rows`, `0 rows`.
 *
 * Trivial on its own; it exists because the same `${n} rows` was written at three separate sites
 * (the Statistics panel header, its row-count line, and the work rail's Statistics row) and every
 * one of them said **"1 rows"** the moment a skill emitted a one-row table. That shape arrived with
 * `confusion`'s agreement scalars and `qq`'s λ (docs/stats-tables/spec.md D4 ranks 3–4) — the
 * product had never had a single-row table before, so no site had ever been asked the question.
 *
 * One home, so the next surface that counts something inherits the answer instead of re-deciding
 * it. English `-s` only: every noun this counts (row, column, table, figure) is regular, and a
 * lookup table of irregulars would be inventing a problem.
 */
export function plural(n: number, noun: string): string {
  return `${n} ${n === 1 ? noun : `${noun}s`}`;
}
