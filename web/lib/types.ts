// Types for the files described in docs/contracts.md.

export interface Source {
  title: string;
  url: string;
}

export type NodeKind =
  | "mine"
  | "refinery"
  | "supplier_major"
  | "supplier_minor"
  | "assembly"
  | "port"
  | "airport"
  | "canal"
  | "border"
  | "apple_store"
  | "carrier"
  | "retailer"
  | "repair"
  | "hq";

export interface NetworkNode {
  id: string;
  name: string;
  kind: NodeKind;
  /** 1 to 7; null when the export marks the production tier unknown. */
  tier: number | null;
  lon: number;
  lat: number;
  precision: "exact" | "city" | "province" | "country";
  region: string;
  ticker: string | null;
  partType: string | null;
  appleRevenueShare: number | null;
  sources: Source[];
  /** Added by the interface (lib/lanes.ts), not from the data files. */
  illustrative?: boolean;
  /** A routing point with no symbol (e.g. where a lane crosses the date line). */
  waypoint?: boolean;
}

export type Mode = "sea" | "air" | "road" | "rail";

export interface NetworkEdge {
  id: string;
  from: string;
  to: string;
  mode: Mode;
  carriesTier: number;
  status: "known" | "inferred";
  sources: Source[];
  via?: [number, number][];
  /** Added by the interface (lib/lanes.ts), not from the data files. */
  illustrative?: boolean;
  /** Drawn only when a scenario uses it as a detour. */
  detourOnly?: boolean;
  /** Node ids this detour goes around. */
  avoids?: string[];
  /** Name for the detour pill when the scenario has no detour option. */
  label?: string;
}

export interface Network {
  snapshotYear: number;
  sampleData: boolean;
  nodes: NetworkNode[];
  edges: NetworkEdge[];
}

export type ScenarioType = "sea" | "sky" | "land" | "policy" | "demand";
export type Range = [number, number];

export interface Prediction {
  nodeId: string;
  pHit: number;
  ciLow: number;
  ciHigh: number;
  lowConfidence: boolean;
  shap: { feature: string; value: number }[];
}

export interface ScenarioOption {
  id: string;
  label: string;
  detail: string;
  unitsRecovered: Range;
  extraCostUsd: Range;
  daysToEffect: number;
  defaultOn: boolean;
  assumption: boolean;
}

export interface Scenario {
  id: string;
  title: string;
  type: ScenarioType;
  start: string;
  end: string;
  snapshotYear: number;
  sampleData: boolean;
  shock: {
    nodeIds: string[];
    capacityLoss: number | null;
    /** Where the shock happened when it is not a node in the network. */
    location?: { lon: number; lat: number; precision?: string; basis?: string };
  };
  headline: string;
  predictions: Prediction[];
  actual: { nodeId: string; hit: boolean; car: number }[];
  options: ScenarioOption[];
  /** Null when the production quota and recovery plan are unknown. */
  quota: {
    weeks: string[];
    target: number[];
    noAction: number[];
    withPlan: number[];
    recoverySentence: string;
  } | null;
  money: { coinUsd: number; revenueAtRisk: Range | null; delayedShare: number | null; assumption: boolean };
  /** Things the export states are not known (e.g. "Physical supplier transport routes"). */
  unknowns?: string[];
  affectedRoutes: { blocked: string[]; detour: string[]; expedited: string[] };
  sensitivity?: { assumption: string; spearman: number }[];
}

export interface ScenarioIndexEntry {
  id: string;
  title: string;
  type: ScenarioType;
  start: string;
}

export interface Metrics {
  model: string;
  events: number;
  rows: number;
  sampleData?: boolean;
  loeo: { eventId: string; auc: number; brier: number; baselineAuc: number }[];
  overall: { auc: Range; brier: Range; baselineAuc: Range };
  calibration: { binMid: number; observed: number; n: number }[];
}

export interface ForecastSeries {
  id: string;
  label: string;
  unit: string;
  source: Source;
  history: { date: string; value: number }[];
  forecast: { date: string; q10: number; q50: number; q90: number }[];
  baseline: { date: string; value: number }[];
  metrics: { mase: number; baselineMase: number; coverage80: number };
}

export interface Forecasts {
  sampleData: boolean;
  series: ForecastSeries[];
}
