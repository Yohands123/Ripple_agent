"use client";

import { useLayoutEffect, useRef, useState, type ReactNode } from "react";
import { size } from "@/lib/tokens";

/**
 * A fixed 1440 × 810 drawing surface (the concept-art frame) scaled to cover
 * its container, so SVG and HTML overlays share one coordinate system.
 */
export default function MapStage({ children }: { children: ReactNode }) {
  const outer = useRef<HTMLDivElement>(null);
  const [fit, setFit] = useState({ scale: 1, x: 0, y: 0 });

  useLayoutEffect(() => {
    const el = outer.current;
    if (!el) return;
    const update = () => {
      const { width, height } = el.getBoundingClientRect();
      const scale = Math.max(width / size.mapW, height / size.mapH);
      setFit({ scale, x: (width - size.mapW * scale) / 2, y: (height - size.mapH * scale) / 2 });
    };
    update();
    const ro = new ResizeObserver(update);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  return (
    <div ref={outer} className="map-stage">
      <div
        className="map-stage-inner"
        style={{
          width: size.mapW,
          height: size.mapH,
          transform: `translate(${fit.x}px, ${fit.y}px) scale(${fit.scale})`,
        }}
      >
        {children}
      </div>
    </div>
  );
}
