"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { loadNetwork, loadScenario, loadScenarioIndex } from "@/lib/data";
import { computeLayout } from "@/lib/layout";
import { buildDisruptionScene } from "@/lib/disruption";
import { daysBetween, monthYear } from "@/lib/format";
import { buildFreeFlowScene, freeFlowEdges } from "@/lib/scene";
import { tierColor, size } from "@/lib/tokens";
import type { Network, Scenario, ScenarioIndexEntry } from "@/lib/types";
import DisruptionPanel from "./DisruptionPanel";
import FreeFlowPanel from "./FreeFlowPanel";
import { Pill } from "./Glyphs";
import MapStage from "./MapStage";
import MoverLayer from "./MoverLayer";
import NodeLayer from "./NodeLayer";
import RouteLayer from "./RouteLayer";
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

  const disrupted = dropped && scenario !== null;

  // Highlighted land: assembly countries, plus the shock country during a disruption.
  const highlight = useMemo(() => {
    const nodes = network?.nodes ?? [];
    const shock = new Set(disrupted ? scenario!.shock.nodeIds : []);
    return nodes.filter((n) => n.kind === "assembly" || shock.has(n.id));
  }, [network, scenario, disrupted]);

  const scene = useMemo(() => {
    if (!network) return null;
    if (disrupted) {
      const layout = computeLayout(network, network.edges);
      return { layout, ...buildDisruptionScene(network, layout, scenario!) };
    }
    const layout = computeLayout(network, freeFlowEdges(network, scenario));
    return { layout, ...buildFreeFlowScene(network, layout, scenario) };
  }, [network, scenario, disrupted]);

  const totalDays = scenario ? Math.max(1, daysBetween(scenario.start, scenario.end)) : 1;
  const day = Math.ceil(totalDays / 2);

  const clear = () => {
    setDropped(false);
    const url = new URL(window.location.href);
    url.searchParams.delete("scenario");
    window.history.pushState(null, "", url);
  };

  const drop = () => {
    if (!scenario) return;
    setDropped(true);
    const url = new URL(window.location.href);
    url.searchParams.set("scenario", scenario.id);
    window.history.pushState(null, "", url);
  };

  const ready = worldReady && (network !== null || networkMissing) && (index.length === 0 || scenario !== null);

  return (
    <div className="app" data-ready={String(ready)} data-mode={disrupted ? "disruption" : "free"}>
      <div className="map-area">
        <MapStage>
          <svg width={size.mapW} height={size.mapH} viewBox={`0 0 ${size.mapW} ${size.mapH}`} aria-hidden="true" className="map-svg">
            <WorldMap highlight={highlight} onLoaded={onWorld} />
            {scene && <RouteLayer routes={scene.routes} money={scene.money} />}
          </svg>
          <div className="map-overlay">
            {scene?.zones?.map((z) => (
              <div key={z.key} className="shock-zone" style={{ left: z.x - z.d / 2, top: z.y - z.d / 2, width: z.d, height: z.d }} />
            ))}
            {network && scene && <NodeLayer network={network} layout={scene.layout} groupText={scene.groupText} />}
            {scene?.captions.map((c) => (
              <div key={c.key} className="map-caption" style={{ left: c.x, top: c.y, width: c.w, color: c.color }}>
                {c.text}
              </div>
            ))}
            {scene && <MoverLayer movers={scene.movers} />}
            {scene?.pills.map((p) => (
              <Pill key={p.key} big={p.big} bg={p.bg} fg={p.fg} style={{ left: p.x, top: p.y }}>
                {p.text}
              </Pill>
            ))}
            {disrupted ? (
              <YearTag text={monthYear(scenario!.start)} subtitle={`Day ${day} of ${totalDays}. ${scenario!.title}`} />
            ) : (
              <>
                <Pill big bg={tierColor[6]} style={{ left: 560, top: 18 }}>
                  ALL LANES CLEAR
                </Pill>
                <YearTag text="NORMAL WEEK" subtitle="Goods flow west, money flows home" />
              </>
            )}
          </div>
        </MapStage>
        {networkMissing && <div className="empty-note">Network data is not available yet.</div>}
      </div>
      <aside className="panel" aria-label="Ripple panel">
        {disrupted ? (
          <DisruptionPanel sample={sample} scenario={scenario!} network={network} onClear={clear} />
        ) : (
          <FreeFlowPanel sample={sample} scenario={scenario} onDrop={drop} />
        )}
      </aside>
    </div>
  );
}
