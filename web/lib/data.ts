// The one data loader. Each file is read from /data/real/ when it exists and
// falls back to /data/fixtures/ (a copy of contracts/fixtures/) otherwise.

import type { Forecasts, Metrics, Network, Scenario, ScenarioIndexEntry } from "./types";

export type DataOrigin = "real" | "fixtures";

export interface Loaded<T> {
  data: T;
  origin: DataOrigin;
}

const ROOTS: DataOrigin[] = ["real", "fixtures"];

async function tryFetch<T>(url: string): Promise<T | null> {
  try {
    const res = await fetch(url, { cache: "no-store" });
    if (!res.ok) return null;
    const type = res.headers.get("content-type") ?? "";
    // Some static hosts answer missing files with an HTML page and status 200.
    if (type.includes("text/html")) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  }
}

/** Loads `relPath` from real data, then fixtures. Returns null when neither exists. */
export async function loadFile<T>(relPath: string): Promise<Loaded<T> | null> {
  for (const origin of ROOTS) {
    const data = await tryFetch<T>(`/data/${origin}/${relPath}`);
    if (data !== null) return { data, origin };
  }
  return null;
}

export const loadNetwork = () => loadFile<Network>("network.json");
export const loadScenarioIndex = () => loadFile<ScenarioIndexEntry[]>("scenarios/index.json");
export const loadScenario = (id: string) => loadFile<Scenario>(`scenarios/${encodeURIComponent(id)}.json`);
export const loadMetrics = () => loadFile<Metrics>("metrics.json");
export const loadForecasts = () => loadFile<Forecasts>("forecasts.json");
