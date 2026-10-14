"use client";

import { useEffect, useRef, useSyncExternalStore } from "react";
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

function positionAt(m: Mover, elapsed: number): [number, number] {
  const [from, to] = m.span ?? [0, m.path.length];
  const len = Math.max(1, to - from);
  const d = from + ((((m.offset - from + m.speed * elapsed) % len) + len) % len);
  return m.path.at(d);
}

function transform(m: Mover, [x, y]: [number, number]): string {
  const w = m.kind === "ship" ? size.shipW : (m.size ?? size.coin);
  const h = m.kind === "ship" ? size.shipH : (m.size ?? size.coin);
  // Ships sit on their lane (hull bottom on the line); coins are centered on it.
  const dx = x - w / 2;
  const dy = m.kind === "ship" ? y - 12 : y - h / 2;
  return `translate(${dx.toFixed(1)}px, ${dy.toFixed(1)}px)${m.rotate ? ` rotate(${m.rotate}deg)` : ""}`;
}

/** Ships and coins travelling along their paths; fixed in place under prefers-reduced-motion. */
export default function MoverLayer({ movers }: { movers: Mover[] }) {
  const reduced = useReducedMotion();
  const refs = useRef(new Map<string, HTMLDivElement>());

  useEffect(() => {
    if (reduced) {
      for (const m of movers) {
        const el = refs.current.get(m.id);
        if (el) el.style.transform = transform(m, positionAt(m, 0));
      }
      return;
    }
    let raf = 0;
    const t0 = performance.now();
    const tick = (now: number) => {
      const elapsed = (now - t0) / 1000;
      for (const m of movers) {
        if (!m.speed) continue;
        const el = refs.current.get(m.id);
        if (el) el.style.transform = transform(m, positionAt(m, elapsed));
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [movers, reduced]);

  return (
    <div className="mover-layer" data-reduced-motion={String(reduced)}>
      {movers.map((m) => {
        const w = m.kind === "ship" ? size.shipW : (m.size ?? size.coin);
        const h = m.kind === "ship" ? size.shipH : (m.size ?? size.coin);
        const style = { width: w, height: h, transform: transform(m, positionAt(m, 0)), opacity: m.opacity ?? 1 };
        const setRef = (el: HTMLDivElement | null) => {
          if (el) refs.current.set(m.id, el);
          else refs.current.delete(m.id);
        };
        return (
          <div key={m.id} ref={setRef} className="mover" data-mover={m.kind} style={style}>
            {m.kind === "ship" ? <Ship /> : <Coin kind={m.coin ?? "gold"} size={m.size ?? size.coin} />}
          </div>
        );
      })}
    </div>
  );
}
