"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { loadForecasts, loadMetrics, loadNetwork, loadScenario, loadScenarioIndex } from "@/lib/data";
import { computeLayout } from "@/lib/layout";
import { buildDisruptionScene } from "@/lib/disruption";
import { daysBetween, monthYear } from "@/lib/format";
import { buildFreeFlowScene, freeFlowEdges } from "@/lib/scene";
import { buildStack } from "@/lib/stack";
import { tierColor, size } from "@/lib/tokens";
import type { Forecasts, Metrics, Network, Scenario, ScenarioIndexEntry } from "@/lib/types";
import DisruptionPanel from "./DisruptionPanel";
import NodeDetailPanel from "./NodeDetailPanel";
import ForecastSection from "./ForecastSection";
import FreeFlowPanel from "./FreeFlowPanel";
import { Pill } from "./Glyphs";
import MapStage from "./MapStage";
import MoverLayer from "./MoverLayer";
import NodeLayer from "./NodeLayer";
import ReplaySection from "./ReplaySection";
import RouteLayer from "./RouteLayer";
import StackOverlay from "./StackOverlay";
import WorldMap from "./WorldMap";
import YearTag from "./YearTag";

function readParam(name: string): string | null {
  if (typeof window === "undefined") return null;
  return new URLSearchParams(window.location.search).get(name);
}

export default function RippleApp() {
  const [network, setNetwork] = useState<Network | null>(null);
  const [networkMissing, setNetworkMissing] = useState(false);
  const [index, setIndex] = useState<ScenarioIndexEntry[]>([]);
  const [scenarioId, setScenarioId] = useState<string | null>(null);
  const [scenario, setScenario] = useState<Scenario | null>(null);
  const [dropped, setDropped] = useState(false);
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [forecasts, setForecasts] = useState<Forecasts | null>(null);
  const [stackId, setStackId] = useState<string | null>(null);
  const [dayChoice, setDayChoice] = useState<{ id: string; day: number } | null>(null);
  const [worldReady, setWorldReady] = useState(false);
  const onWorld = useCallback(() => setWorldReady(true), []);

  useEffect(() => {
    loadNetwork().then((res) => {
      const nodeParam = readParam("node");
      const fromUrl = res && nodeParam ? res.data.nodes.find((n) => n.id === nodeParam) : undefined;
      if (fromUrl) {
        setSelectedId(fromUrl.id);
        if (fromUrl.kind === "assembly" && readParam("stack") !== "0") setStackId(fromUrl.id);
      }
      if (res) setNetwork(res.data);
      else setNetworkMissing(true);
    });
    loadMetrics().then((res) => setMetrics(res?.data ?? null));
    loadForecasts().then((res) => setForecasts(res?.data ?? null));
    loadScenarioIndex().then((res) => {
      const list = res?.data ?? [];
      setIndex(list);
      const fromUrl = readParam("scenario");
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

  const sample = Boolean(network?.sampleData || scenario?.sampleData || metrics?.sampleData);

  const disrupted = dropped && scenario !== null;
  const totalDays = scenario ? Math.max(1, daysBetween(scenario.start, scenario.end)) : 1;
  const day = scenario && dayChoice?.id === scenario.id ? dayChoice.day : Math.ceil(totalDays / 2);
  // Effects build over the first half of the event (the concept art shows day 3 of 6 at full effect).
  const progress = Math.min(1, day / Math.ceil(totalDays / 2));
  const eventOver = day >= totalDays;

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
      return { layout, ...buildDisruptionScene(network, layout, scenario!, progress, eventOver) };
    }
    const layout = computeLayout(network, freeFlowEdges(network, scenario));
    return { layout, ...buildFreeFlowScene(network, layout, scenario) };
  }, [network, scenario, disrupted, progress, eventOver]);


  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setStackId(null);
        setSelectedId(null);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const selectedNode = network?.nodes.find((n) => n.id === selectedId) ?? null;
  const stack = useMemo(() => (network && stackId ? buildStack(network, stackId, scenario, disrupted) : null), [network, stackId, scenario, disrupted]);

  // Clicking an assembly factory opens its supplier stack as well as its details.
  const selectNode = useCallback(
    (id: string | null) => {
      setSelectedId(id);
      const n = network?.nodes.find((x) => x.id === id);
      if (n?.kind === "assembly") setStackId(n.id);
    },
    [network],
  );

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
            {network && scene && <NodeLayer network={network} layout={scene.layout} groupText={scene.groupText} selectedId={selectedId} onSelect={selectNode} />}
            {scene?.captions.map((c) => (
              <div key={c.key} className="map-caption" style={{ left: c.x, top: c.y, width: c.w, color: c.color }}>
                {c.text}
              </div>
            ))}
            {scene?.markers?.map((m) => (
              <div
                key={m.key}
                className={`map-marker ${m.kind}${m.low ? " low" : ""}`}
                data-marker={m.kind}
                style={{ left: m.x - m.r, top: m.y - m.r, width: 2 * m.r, height: 2 * m.r }}
              />
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
        {stack && <StackOverlay stack={stack} onClose={() => setStackId(null)} onSelectNode={(id) => setSelectedId(id)} />}
      </div>
      <aside className="panel" aria-label="Ripple panel">
        {selectedNode ? (
          <NodeDetailPanel sample={sample || Boolean(forecasts?.sampleData)} node={selectedNode} scenario={scenario} onClose={() => setSelectedId(null)}>
            <ForecastSection forecasts={forecasts} />
          </NodeDetailPanel>
        ) : disrupted ? (
          <DisruptionPanel sample={sample} scenario={scenario!} network={network} onClear={clear} showActual={eventOver} onSelectNode={selectNode}>
            <ReplaySection
              scenario={scenario!}
              metrics={metrics}
              day={day}
              totalDays={totalDays}
              onDay={(d) => setDayChoice({ id: scenario!.id, day: d })}
            />
          </DisruptionPanel>
        ) : (
          <FreeFlowPanel sample={sample} scenario={scenario} onDrop={drop} />
        )}
      </aside>
    </div>
  );
}
