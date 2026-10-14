"use client";

import { useCallback, useEffect, useLayoutEffect, useRef, useState, type ReactNode } from "react";
import { WORLD_BOUNDS, type Pt } from "@/lib/geo";
import { size } from "@/lib/tokens";

/**
 * The map drawn in the concept-art pixel space (1440 × 810 is the default view),
 * with the whole world around it. Drag to pan; wheel, pinch, or the buttons to zoom.
 * `hud` is drawn in screen space on top (year tag, status pill, pinned cards).
 */

export interface View {
  /** Content point at the centre of the screen. */
  cx: number;
  cy: number;
  /** Zoom relative to the default view. */
  k: number;
}

export interface StageInfo {
  view: View;
  /** Container size in px. */
  w: number;
  h: number;
  /** Base scale that fits the 1440 × 810 default view in the container. */
  s: number;
  /** Is a content point currently on screen (with a margin in screen px)? */
  isVisible: (p: Pt, margin?: number) => boolean;
  /** Centre the view on a content point. */
  goTo: (p: Pt, k?: number) => void;
}

const DEFAULT_VIEW: View = { cx: size.mapW / 2, cy: size.mapH / 2, k: 1 };
const K_MAX = 4;
const DRAG_THRESHOLD = 4;

interface Props {
  children: ReactNode;
  hud?: (info: StageInfo) => ReactNode;
}

export default function MapStage({ children, hud }: Props) {
  const outer = useRef<HTMLDivElement>(null);
  const [box, setBox] = useState({ w: size.mapW, h: size.mapH });
  const [view, setView] = useState<View>(DEFAULT_VIEW);

  useLayoutEffect(() => {
    const el = outer.current;
    if (!el) return;
    const update = () => {
      const r = el.getBoundingClientRect();
      if (r.width > 0 && r.height > 0) setBox({ w: r.width, h: r.height });
    };
    update();
    const ro = new ResizeObserver(update);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // Base scale: the whole default view fits; extra space shows more of the world.
  const s = Math.min(box.w / size.mapW, box.h / size.mapH);

  const clamp = useCallback(
    (v: View): View => {
      const worldW = WORLD_BOUNDS.x1 - WORLD_BOUNDS.x0;
      const worldH = WORLD_BOUNDS.y1 - WORLD_BOUNDS.y0;
      const kMin = Math.min(1, Math.max(box.w / (s * worldW), box.h / (s * worldH)));
      const k = Math.min(K_MAX, Math.max(kMin, v.k));
      const halfW = box.w / (2 * s * k);
      const halfH = box.h / (2 * s * k);
      const cx = Math.min(WORLD_BOUNDS.x1 - halfW, Math.max(WORLD_BOUNDS.x0 + halfW, v.cx));
      const cy = Math.min(WORLD_BOUNDS.y1 - halfH, Math.max(WORLD_BOUNDS.y0 + halfH, v.cy));
      return { cx, cy, k };
    },
    [box, s],
  );

  const v = clamp(view);
  const scale = s * v.k;

  // Zoom keeping the content point under (sx, sy) fixed.
  const zoomAt = useCallback(
    (factor: number, sx: number, sy: number) => {
      setView((prev) => {
        const p = clamp(prev);
        const sc = s * p.k;
        const px = (sx - box.w / 2) / sc + p.cx;
        const py = (sy - box.h / 2) / sc + p.cy;
        const k = Math.min(K_MAX, p.k * factor);
        const sc2 = s * k;
        return clamp({ k, cx: px - (sx - box.w / 2) / sc2, cy: py - (sy - box.h / 2) / sc2 });
      });
    },
    [box, s, clamp],
  );

  // Wheel zoom (non-passive so the page does not scroll).
  useEffect(() => {
    const el = outer.current;
    if (!el) return;
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      const r = el.getBoundingClientRect();
      zoomAt(Math.exp(-e.deltaY * 0.0015), e.clientX - r.left, e.clientY - r.top);
    };
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  }, [zoomAt]);

  // Drag to pan, two fingers to pinch. Pointer capture starts only once a drag
  // passes the threshold, so plain clicks still reach nodes.
  const pointers = useRef(new Map<number, { x: number; y: number }>());
  const drag = useRef<{ x: number; y: number; moved: boolean; pinch: number | null }>({ x: 0, y: 0, moved: false, pinch: null });

  const onPointerDown = (e: React.PointerEvent) => {
    if ((e.target as HTMLElement).closest(".map-hud-controls")) return;
    pointers.current.set(e.pointerId, { x: e.clientX, y: e.clientY });
    if (pointers.current.size === 1) drag.current = { x: e.clientX, y: e.clientY, moved: false, pinch: null };
    if (pointers.current.size === 2) {
      const [a, b] = [...pointers.current.values()];
      drag.current.pinch = Math.hypot(a.x - b.x, a.y - b.y);
    }
  };

  const onPointerMove = (e: React.PointerEvent) => {
    const prev = pointers.current.get(e.pointerId);
    if (!prev) return;
    const r = outer.current!.getBoundingClientRect();
    pointers.current.set(e.pointerId, { x: e.clientX, y: e.clientY });
    if (pointers.current.size === 2 && drag.current.pinch) {
      const [a, b] = [...pointers.current.values()];
      const dist = Math.hypot(a.x - b.x, a.y - b.y);
      zoomAt(dist / drag.current.pinch, (a.x + b.x) / 2 - r.left, (a.y + b.y) / 2 - r.top);
      drag.current.pinch = dist;
      drag.current.moved = true;
      return;
    }
    if (!drag.current.moved && Math.hypot(e.clientX - drag.current.x, e.clientY - drag.current.y) < DRAG_THRESHOLD) return;
    if (!drag.current.moved) {
      drag.current.moved = true;
      outer.current?.setPointerCapture(e.pointerId);
    }
    const dx = e.clientX - prev.x;
    const dy = e.clientY - prev.y;
    setView((p) => {
      const c = clamp(p);
      return clamp({ ...c, cx: c.cx - dx / (s * c.k), cy: c.cy - dy / (s * c.k) });
    });
  };

  const onPointerUp = (e: React.PointerEvent) => {
    pointers.current.delete(e.pointerId);
    if (pointers.current.size < 2) drag.current.pinch = null;
  };

  // Swallow the click that ends a drag so it does not select a node.
  const onClickCapture = (e: React.MouseEvent) => {
    if (drag.current.moved) {
      e.stopPropagation();
      e.preventDefault();
      drag.current.moved = false;
    }
  };

  const onKeyDown = (e: React.KeyboardEvent) => {
    const step = 80 / (s * v.k);
    const pan = (dx: number, dy: number) => setView((p) => clamp({ ...clamp(p), cx: clamp(p).cx + dx, cy: clamp(p).cy + dy }));
    if (e.key === "ArrowLeft") pan(-step, 0);
    else if (e.key === "ArrowRight") pan(step, 0);
    else if (e.key === "ArrowUp") pan(0, -step);
    else if (e.key === "ArrowDown") pan(0, step);
    else if (e.key === "+" || e.key === "=") zoomAt(1.4, box.w / 2, box.h / 2);
    else if (e.key === "-" || e.key === "_") zoomAt(1 / 1.4, box.w / 2, box.h / 2);
    else if (e.key === "0") setView(DEFAULT_VIEW);
    else return;
    e.preventDefault();
  };

  const info: StageInfo = {
    view: v,
    w: box.w,
    h: box.h,
    s,
    isVisible: ([x, y], margin = 0) => {
      const sx = (x - v.cx) * scale + box.w / 2;
      const sy = (y - v.cy) * scale + box.h / 2;
      return sx >= -margin && sy >= -margin && sx <= box.w + margin && sy <= box.h + margin;
    },
    goTo: (p, k = 1) => setView(clamp({ cx: p[0], cy: p[1], k })),
  };

  const isDefault = Math.abs(v.k - 1) < 1e-3 && Math.abs(v.cx - DEFAULT_VIEW.cx) < 0.5 && Math.abs(v.cy - DEFAULT_VIEW.cy) < 0.5;

  return (
    <div
      ref={outer}
      className="map-stage"
      tabIndex={0}
      role="application"
      aria-label="Map. Drag or use arrow keys to pan; scroll, pinch, or plus and minus keys to zoom; 0 resets the view."
      data-view={`${v.cx.toFixed(1)},${v.cy.toFixed(1)},${v.k.toFixed(3)}`}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
      onPointerCancel={onPointerUp}
      onClickCapture={onClickCapture}
      onKeyDown={onKeyDown}
    >
      <div
        className="map-stage-inner"
        style={{
          width: size.mapW,
          height: size.mapH,
          transform: `translate(${box.w / 2}px, ${box.h / 2}px) scale(${scale}) translate(${-v.cx}px, ${-v.cy}px)`,
        }}
      >
        {children}
      </div>
      <div className="map-hud" style={{ width: box.w / s, height: box.h / s, transform: `scale(${s})` }}>
        {hud?.(info)}
        <div className="map-hud-controls">
          <button type="button" aria-label="Zoom in" onClick={() => zoomAt(1.5, box.w / 2, box.h / 2)}>
            +
          </button>
          <button type="button" aria-label="Zoom out" onClick={() => zoomAt(1 / 1.5, box.w / 2, box.h / 2)}>
            −
          </button>
          <button type="button" className="reset" onClick={() => setView(DEFAULT_VIEW)} disabled={isDefault}>
            Reset view
          </button>
        </div>
      </div>
    </div>
  );
}
