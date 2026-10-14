// Sampled paths that movers (ships, coins) travel along.

import type { Pt } from "./geo";

export class Polyline {
  readonly pts: Pt[];
  readonly cum: number[];
  readonly length: number;

  constructor(pts: Pt[]) {
    this.pts = pts;
    this.cum = [0];
    for (let i = 1; i < pts.length; i++) {
      this.cum.push(this.cum[i - 1] + Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]));
    }
    this.length = this.cum[this.cum.length - 1] ?? 0;
  }

  /** Point at distance `d` from the start (clamped). */
  at(d: number): Pt {
    const { pts, cum } = this;
    if (pts.length === 0) return [0, 0];
    if (d <= 0) return pts[0];
    if (d >= this.length) return pts[pts.length - 1];
    let lo = 0;
    let hi = cum.length - 1;
    while (hi - lo > 1) {
      const mid = (lo + hi) >> 1;
      if (cum[mid] <= d) lo = mid;
      else hi = mid;
    }
    const seg = cum[hi] - cum[lo] || 1;
    const t = (d - cum[lo]) / seg;
    return [pts[lo][0] + (pts[hi][0] - pts[lo][0]) * t, pts[lo][1] + (pts[hi][1] - pts[lo][1]) * t];
  }

  /** Point at fraction `f` (0..1) of the length. */
  atFraction(f: number): Pt {
    return this.at(f * this.length);
  }

  /** Distance along the path of the sampled point nearest to `p`. */
  project(p: Pt): number {
    let best = 0;
    let bestD = Infinity;
    this.pts.forEach((q, i) => {
      const dd = (q[0] - p[0]) ** 2 + (q[1] - p[1]) ** 2;
      if (dd < bestD) {
        bestD = dd;
        best = this.cum[i];
      }
    });
    return best;
  }

  /** The part of the path between two distances. */
  slice(from: number, to: number): Polyline {
    const inner = this.pts.filter((_, i) => this.cum[i] > from && this.cum[i] < to);
    return new Polyline([this.at(from), ...inner, this.at(to)]);
  }
}

/** Cubic Bézier samples of a uniform Catmull-Rom spline through `pts`. */
export function sampleSmooth(pts: Pt[], step = 6): Pt[] {
  if (pts.length < 2) return [...pts];
  const out: Pt[] = [];
  for (let i = 0; i < pts.length - 1; i++) {
    const p0 = pts[Math.max(0, i - 1)];
    const p1 = pts[i];
    const p2 = pts[i + 1];
    const p3 = pts[Math.min(pts.length - 1, i + 2)];
    const c1: Pt = [p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6];
    const c2: Pt = [p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6];
    const n = Math.max(2, Math.ceil(Math.hypot(p2[0] - p1[0], p2[1] - p1[1]) / step));
    for (let j = i === 0 ? 0 : 1; j <= n; j++) {
      const t = j / n;
      const u = 1 - t;
      out.push([
        u * u * u * p1[0] + 3 * u * u * t * c1[0] + 3 * u * t * t * c2[0] + t * t * t * p2[0],
        u * u * u * p1[1] + 3 * u * u * t * c1[1] + 3 * u * t * t * c2[1] + t * t * t * p2[1],
      ]);
    }
  }
  return out;
}

/** Quadratic Bézier samples from a through control c to b. */
export function sampleQuad(a: Pt, c: Pt, b: Pt, step = 6): Pt[] {
  const n = Math.max(2, Math.ceil(Math.hypot(b[0] - a[0], b[1] - a[1]) / step));
  return Array.from({ length: n + 1 }, (_, i) => {
    const t = i / n;
    const u = 1 - t;
    return [u * u * a[0] + 2 * u * t * c[0] + t * t * b[0], u * u * a[1] + 2 * u * t * c[1] + t * t * b[1]] as Pt;
  });
}
