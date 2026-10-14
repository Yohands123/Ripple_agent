/** $500M, $1.2B, $40K. */
export function formatUsd(v: number): string {
  const abs = Math.abs(v);
  const fmt = (n: number, unit: string) => `$${Number.isInteger(n) ? n : n.toFixed(1)}${unit}`;
  if (abs >= 1e9) return fmt(+(v / 1e9).toFixed(1), "B");
  if (abs >= 1e6) return fmt(+(v / 1e6).toFixed(1), "M");
  if (abs >= 1e3) return fmt(+(v / 1e3).toFixed(1), "K");
  return `$${v}`;
}

const MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"];

/** "2021-03-23" → "MAR 2021" */
export function monthYear(iso: string): string {
  const [y, m] = iso.split("-").map(Number);
  return `${MONTHS[m - 1]} ${y}`;
}

/** Whole days between two ISO dates. */
export function daysBetween(a: string, b: string): number {
  return Math.round((Date.parse(b) - Date.parse(a)) / 86_400_000);
}
