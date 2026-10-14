"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { loadNetwork, loadScenario, loadScenarioIndex } from "@/lib/data";
import { computeLayout } from "@/lib/layout";
import { tierColor, size } from "@/lib/tokens";
import type { Network, Scenario, ScenarioIndexEntry } from "@/lib/types";
import FreeFlowPanel from "./FreeFlowPanel";
import { Pill } from "./Glyphs";
import MapStage from "./MapStage";
import NodeLayer from "./NodeLayer";
import WorldMap from "./WorldMap";
import YearTag from "./YearTag";

function readScenarioParam(): string | null {
  if (typeof window === "undefined") return null;
  return new URLSearchParams(window.location.search).get("scenario");
}

export default function RippleApp() {
  const [network, setNetwork] = useState<Network | null>(null);
  const [networkMissing, setNetworkMissing] = useState(false);
  const [index, setIndex] = useState<ScenarioIndexEntry[]>([]);
  const [scenarioId, setScenarioId] = useState<string | null>(null);
  const [scenario, setScenario] = useState<Scenario | null>(null);
  const [dropped, setDropped] = useState(false);
  const [worldReady, setWorldReady] = useState(false);
  const onWorld = useCallback(() => setWorldReady(true), []);

  useEffect(() => {
    loadNetwork().then((res) => {
      if (res) setNetwork(res.data);
      else setNetworkMissing(true);
    });
    loadScenarioIndex().then((res) => {
      const list = res?.data ?? [];
      setIndex(list);
      const fromUrl = readScenarioParam();
      const pick = list.find((s) => s.id === fromUrl) ?? list[0];
      if (pick) setScenarioId(pick.id);
      if (fromUrl && pick?.id === fromUrl) setDropped(true);
    });
  }, []);

  useEffect(() => {
    if (!scenarioId) return;
    let live = true;
    loadScenario(scenarioId).then((res) => live && setScenario(res?.data ?? null));
    return () => {
      live = false;
    };
  }, [scenarioId]);

  const sample = Boolean(network?.sampleData || scenario?.sampleData);

  const highlight = useMemo(() => (network?.nodes ?? []).filter((n) => n.kind === "assembly"), [network]);

  const layout = useMemo(() => (network ? computeLayout(network, []) : null), [network]);

  const drop = () => {
    if (!scenario) return;
    setDropped(true);
    const url = new URL(window.location.href);
    url.searchParams.set("scenario", scenario.id);
    window.history.pushState(null, "", url);
  };

  const ready = worldReady && (network !== null || networkMissing) && (index.length === 0 || scenario !== null);

  return (
    <div className="app" data-ready={String(ready)} data-mode={dropped ? "disruption" : "free"}>
      <div className="map-area">
        <MapStage>
          <svg width={size.mapW} height={size.mapH} viewBox={`0 0 ${size.mapW} ${size.mapH}`} aria-hidden="true" className="map-svg">
            <WorldMap highlight={highlight} onLoaded={onWorld} />
          </svg>
          <div className="map-overlay">
            {network && layout && <NodeLayer network={network} layout={layout} />}
            <Pill big bg={tierColor[6]} style={{ left: 560, top: 18 }}>
              ALL LANES CLEAR
            </Pill>
            <YearTag text="NORMAL WEEK" subtitle="Goods flow west, money flows home" />
          </div>
        </MapStage>
        {networkMissing && <div className="empty-note">Network data is not available yet.</div>}
      </div>
      <aside className="panel" aria-label="Ripple panel">
        <FreeFlowPanel sample={sample} scenario={scenario} onDrop={drop} />
      </aside>
    </div>
  );
}
