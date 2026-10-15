"use client";

import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import { WORLD_BOUNDS, loadWorld } from "@/lib/geo";
import type { Mover } from "@/lib/scene";
import { size } from "@/lib/tokens";
import { Coin, Ship } from "./Glyphs";

const QUERY = "(prefers-reduced-motion: reduce)";

function subscribe(cb: () => void) {
  const mq = window.matchMedia(QUERY);
  mq.addEventListener("change", cb);
  return () => mq.removeEventListener("change", cb);
}

export function useReducedMotion(): boolean {
  return useSyncExternalStore(
    subscribe,
    () => window.matchMedia(QUERY).matches,
    () => false,
  );
}

/** Land as a bitmap in map pixels (half resolution), for keeping ships off land. */
export interface LandMask {
  isLand: (x: number, y: number) => boolean;
}

let maskPromise: Promise<LandMask | null> | null = null;

export function loadLandMask(): Promise<LandMask | null> {
  if (!maskPromise) {
    maskPromise = loadWorld().then((world) => {
      if (typeof document === "undefined") return null;
      const f = 0.5;
      const w = Math.ceil((WORLD_BOUNDS.x1 - WORLD_BOUNDS.x0) * f);
      const h = Math.ceil((WORLD_BOUNDS.y1 - WORLD_BOUNDS.y0) * f);
      const canvas = document.createElement("canvas");
      canvas.width = w;
      canvas.height = h;
      const ctx = canvas.getContext("2d", { willReadFrequently: true });
      if (!ctx) return null;
      ctx.setTransform(f, 0, 0, f, -WORLD_BOUNDS.x0 * f, -WORLD_BOUNDS.y0 * f);
      ctx.fill(new Path2D(world.land));
      const data = ctx.getImageData(0, 0, w, h).data;
      return {
        isLand: (x, y) => {
          const px = Math.floor((x - WORLD_BOUNDS.x0) * f);
          const py = Math.floor((y - WORLD_BOUNDS.y0) * f);
          if (px < 0 || py < 0 || px >= w || py >= h) return false;
          return data[(py * w + px) * 4 + 3] > 128;
        },
      };
    });
  }
  return maskPromise;
}

interface Place {
  x: number;
  y: number;
  /** Progress through the travel span, 0..1. */
  frac: number;
}

function positionAt(m: Mover, elapsed: number): Place {
  const [from, to] = m.span ?? [0, m.path.length];
  const len = Math.max(1, to - from);
  const along = (((m.offset - from + m.speed * elapsed) % len) + len) % len;
  const [x, y] = m.path.at(from + along);
  return { x, y, frac: along / len };
}

function apply(el: HTMLDivElement, m: Mover, p: Place, mask: LandMask | null) {
  el.style.transform = transform(m, p);
  if (m.fall) el.style.opacity = String(1 - 0.6 * p.frac);
  // Ships never sail over land: one passing a headland or a port's land connector is hidden there.
  // (The queue and the stuck ship are placed by hand at a narrow chokepoint, which the coarse land outline may cover.)
  if (m.kind === "ship" && mask && !m.enter && m.rotate == null) el.style.visibility = mask.isLand(p.x, p.y) ? "hidden" : "";
}

function transform(m: Mover, { x, y, frac }: Place): string {
  const w = m.kind === "ship" ? size.shipW : (m.size ?? size.coin);
  const h = m.kind === "ship" ? size.shipH : (m.size ?? size.coin);
  // Ships sit on their lane (hull bottom on the line); coins are centered on it.
  const dx = x - w / 2;
  const dy = m.kind === "ship" ? y - 12 : y - h / 2;
  const turn = m.fall ? (m.rotate ?? 0) * frac : m.rotate;
  return `translate(${dx.toFixed(1)}px, ${dy.toFixed(1)}px)${turn ? ` rotate(${turn.toFixed(1)}deg)` : ""}`;
}

/** Ships and coins travelling along their paths; fixed in place under prefers-reduced-motion. */
export default function MoverLayer({ movers }: { movers: Mover[] }) {
  const reduced = useReducedMotion();
  const refs = useRef(new Map<string, HTMLDivElement>());
  const [mask, setMask] = useState<LandMask | null>(null);
  useEffect(() => {
    let live = true;
    loadLandMask().then((m) => live && setMask(m));
    return () => {
      live = false;
    };
  }, []);

  useEffect(() => {
    if (reduced) {
      for (const m of movers) {
        const el = refs.current.get(m.id);
        if (el) apply(el, m, positionAt(m, 0), mask);
      }
      return;
    }
    let raf = 0;
    const t0 = performance.now();
    const tick = (now: number) => {
      const elapsed = (now - t0) / 1000;
      for (const m of movers) {
        if (!m.speed && elapsed > 0.05) continue;
        const el = refs.current.get(m.id);
        if (el) apply(el, m, positionAt(m, elapsed), mask);
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [movers, reduced, mask]);

  return (
    <div className="mover-layer" data-reduced-motion={String(reduced)}>
      {movers.map((m) => {
        const w = m.kind === "ship" ? size.shipW : (m.size ?? size.coin);
        const h = m.kind === "ship" ? size.shipH : (m.size ?? size.coin);
        const start = positionAt(m, 0);
        const style = { width: w, height: h, transform: transform(m, start), opacity: m.fall ? 1 - 0.6 * start.frac : (m.opacity ?? 1) };
        const setRef = (el: HTMLDivElement | null) => {
          if (el) refs.current.set(m.id, el);
          else refs.current.delete(m.id);
        };
        return (
          <div key={m.id} ref={setRef} className={m.enter ? `mover ${m.enter}` : "mover"} data-mover={m.kind} data-coin={m.coin} style={style}>
            {m.kind === "ship" ? <Ship /> : <Coin kind={m.coin ?? "gold"} size={m.size ?? size.coin} />}
          </div>
        );
      })}
    </div>
  );
}
