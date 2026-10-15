"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { loadForecasts, loadMetrics, loadNetwork, loadNetworkAt, loadScenario, loadScenarioIndex } from "@/lib/data";
import { computeLayout, withZoomLabels } from "@/lib/layout";
import { project } from "@/lib/geo";
import { needsIllustrativeLanes, withIllustrativeEffects, withIllustrativeLanes } from "@/lib/lanes";
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
import ScenarioPicker from "./ScenarioPicker";
import RouteLayer from "./RouteLayer";
import StackOverlay from "./StackOverlay";
import WorldMap from "./WorldMap";
import YearTag from "./YearTag";

function readParam(name: string): string | null {
  if (typeof window === "undefined") return null;
  return new URLSearchParams(window.location.search).get(name);
}

export default function RippleApp() {
  const [defaultNetwork, setNetwork] = useState<Network | null>(null);
  // The dropped event's own network: each event uses the Supplier List from its own year.
  const [eventNetwork, setEventNetwork] = useState<{ id: string; network: Network } | null>(null);
  const [networkMissing, setNetworkMissing] = useState(false);
  const [index, setIndex] = useState<ScenarioIndexEntry[]>([]);
  const [scenarioId, setScenarioId] = useState<string | null>(null);
  const [rawScenario, setScenario] = useState<Scenario | null>(null);
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
    loadScenario(scenarioId).then((res) => {
      if (!live) return;
      setScenario(res?.data ?? null);
      const path = res?.data.networkPath;
      if (res && path) loadNetworkAt(res.origin, path).then((net) => live && net && setEventNetwork({ id: res.data.id, network: net }));
    });
    return () => {
      live = false;
    };
  }, [scenarioId]);

  const rawNetwork = dropped && rawScenario && eventNetwork?.id === rawScenario.id ? eventNetwork.network : defaultNetwork;
  // With no routes in the data, typical lanes stand in so the map keeps its sea lanes, ships, and flights.
  const network = useMemo(() => (rawNetwork ? withIllustrativeLanes(rawNetwork) : null), [rawNetwork]);
  const illustrative = Boolean(rawNetwork && needsIllustrativeLanes(rawNetwork));
  const scenario = useMemo(() => (rawScenario && network ? withIllustrativeEffects(rawScenario, network) : rawScenario), [rawScenario, network]);
  const lanesNote = illustrative ? (
    <div className="panel-tiny" data-note="illustrative-lanes">
      Dashed lanes, ships, and flights are typical routes from public geography, not supplier-specific: the data does not include transport routes.
    </div>
  ) : null;

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
    const points: { lon: number; lat: number }[] = nodes.filter((n) => n.kind === "assembly" || shock.has(n.id));
    const loc = disrupted ? scenario!.shock.location : undefined;
    if (loc) points.push({ lon: loc.lon, lat: loc.lat });
    return points;
  }, [network, scenario, disrupted]);

  // A dropped event's shock is brought into view when it is off screen (e.g. Japan from the concept view).
  const focusPoint = useMemo(() => {
    if (!disrupted || !network) return null;
    const loc = scenario!.shock.location;
    const node = network.nodes.find((n) => n.id === scenario!.shock.nodeIds[0]);
    const at = loc ?? node;
    return at ? { key: scenario!.id, point: project(at.lon, at.lat) } : null;
  }, [disrupted, network, scenario]);

  const scene = useMemo(() => {
    if (!network) return null;
    // Zoom labels are added once every scene pill has its place.
    if (disrupted) {
      const layout = computeLayout(network, network.edges);
      const built = buildDisruptionScene(network, layout, scenario!, progress, eventOver);
      return { layout: { ...layout, labels: withZoomLabels(layout) }, ...built };
    }
    const layout = computeLayout(network, freeFlowEdges(network, scenario));
    const built = buildFreeFlowScene(network, layout, scenario);
    return { layout: { ...layout, labels: withZoomLabels(layout) }, ...built };
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

  const pickScenario = (id: string) => {
    setScenarioId(id);
    setStackId(null);
    if (dropped) {
      const url = new URL(window.location.href);
      url.searchParams.set("scenario", id);
      window.history.replaceState(null, "", url);
    }
  };

  // With a single scenario there is nothing to pick, and the panels match the concept art.
  const picker = index.length > 1 ? <ScenarioPicker index={index} selectedId={scenarioId} onSelect={pickScenario} /> : null;

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
        <MapStage
          focus={focusPoint}
          hud={(stage) => (
            <>
              {scene?.layout.hq?.offMap && !stage.isVisible(scene.layout.hq.anchor, -40) && (
                <button
                  type="button"
                  className="hq-card hq-pinned"
                  style={{ left: scene.layout.hq.pin.x, top: scene.layout.hq.pin.y }}
                  onClick={() => stage.goTo(scene.layout.hq!.anchor)}
                  title="Go to Apple Park"
                >
                  APPLE PARK
                  <br />
                  CUPERTINO
                </button>
              )}
              {disrupted ? (
                <YearTag text={monthYear(scenario!.start)} subtitle={`Day ${day} of ${totalDays}. ${scenario!.title}`} />
              ) : (
                <>
                  <Pill big bg={tierColor[6]} style={{ left: `${(560 / size.mapW) * 100}%`, top: 18 }}>
                    ALL LANES CLEAR
                  </Pill>
                  <YearTag text="NORMAL WEEK" subtitle="Goods flow west, money flows home" />
                </>
              )}
            </>
          )}
        >
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
          <DisruptionPanel sample={sample} scenario={scenario!} network={network} onClear={clear} showActual={eventOver} onSelectNode={selectNode} picker={picker}>
            {lanesNote}
            <ReplaySection
              scenario={scenario!}
              metrics={metrics}
              day={day}
              totalDays={totalDays}
              onDay={(d) => setDayChoice({ id: scenario!.id, day: d })}
            />
          </DisruptionPanel>
        ) : (
          <FreeFlowPanel sample={sample} scenario={scenario} onDrop={drop}>
            {lanesNote}
            {picker}
          </FreeFlowPanel>
        )}
      </aside>
    </div>
  );
}
