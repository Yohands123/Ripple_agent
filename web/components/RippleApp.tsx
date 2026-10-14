"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { loadNetwork, type Loaded } from "@/lib/data";
import type { Network } from "@/lib/types";
import { size } from "@/lib/tokens";
import MapStage from "./MapStage";
import WorldMap from "./WorldMap";

export default function RippleApp() {
  const [network, setNetwork] = useState<Loaded<Network> | null>(null);

  const [worldReady, setWorldReady] = useState(false);
  const onWorld = useCallback(() => setWorldReady(true), []);

  useEffect(() => {
    loadNetwork().then(setNetwork);
  }, []);

  const highlight = useMemo(
    () => (network?.data.nodes ?? []).filter((n) => n.kind === "assembly"),
    [network],
  );

  return (
    <div className="app" data-ready={String(worldReady && network !== null)}>
      <div className="map-area">
        <MapStage>
          <svg width={size.mapW} height={size.mapH} viewBox={`0 0 ${size.mapW} ${size.mapH}`} aria-hidden="true" className="map-svg">
            <WorldMap highlight={highlight} onLoaded={onWorld} />
          </svg>
        </MapStage>
      </div>
      <aside className="panel" aria-label="Ripple panel" />
    </div>
  );
}
