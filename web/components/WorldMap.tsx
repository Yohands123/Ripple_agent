"use client";

import { useEffect, useMemo, useState } from "react";
import { countryAt, countryPath, loadWorld, WORLD_BOUNDS, type WorldGeometry } from "@/lib/geo";
import { color } from "@/lib/tokens";

export interface HighlightPoint {
  lon: number;
  lat: number;
}

/** Ocean, Natural Earth land, and highlighted countries (those containing any of `highlight`). */
export default function WorldMap({ highlight, onLoaded }: { highlight: HighlightPoint[]; onLoaded?: () => void }) {
  const [world, setWorld] = useState<WorldGeometry | null>(null);

  useEffect(() => {
    let live = true;
    loadWorld().then((w) => {
      if (!live) return;
      setWorld(w);
      onLoaded?.();
    });
    return () => {
      live = false;
    };
  }, [onLoaded]);

  const highlightPaths = useMemo(() => {
    if (!world) return [];
    const seen = new Map<string, string>();
    for (const p of highlight) {
      const c = countryAt(world, p.lon, p.lat);
      if (c && !seen.has(c.id)) seen.set(c.id, countryPath(c));
    }
    return [...seen.entries()];
  }, [world, highlight]);

  return (
    <g data-layer="world">
      <rect x={WORLD_BOUNDS.x0} y={WORLD_BOUNDS.y0} width={WORLD_BOUNDS.x1 - WORLD_BOUNDS.x0} height={WORLD_BOUNDS.y1 - WORLD_BOUNDS.y0} fill={color.ocean} />
      {world && <path d={world.land} fill={color.land} stroke={color.landStroke} strokeWidth={1} strokeLinejoin="round" />}
      {highlightPaths.map(([id, d]) => (
        <path key={id} d={d} fill={color.landHighlight} />
      ))}
    </g>
  );
}
