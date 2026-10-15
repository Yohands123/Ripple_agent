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
  | "hq"
  | "sales_region"
  | "chokepoint"
  | "event_anchor";

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
  /** How the tier is known: stated in a source, mapped from part type, or unknown. */
  tierStatus?: "known" | "inferred" | "unknown";
  tierBasis?: string;
  companyId?: string;
  locationRole?: string;
  partTypeScope?: string;
  /** `supplier` for the year's disclosed sites, `backbone` for dated reference geography. */
  layer?: string;
  /** Qualitative confidence in an inferred classification (not a probability). */
  confidence?: string;
  confidenceKind?: string;
  canonicalCompany?: string;
  salesRegion?: string;
  /** Added by the interface (lib/lanes.ts), not from the data files. */
  illustrative?: boolean;
  /** A routing point with no symbol (e.g. where a lane crosses the date line). */
  waypoint?: boolean;
  /** `minerals` (mining regions, refineries) or `returns` (repair and recycling): dated display context, not the year's roster. */
  contextLayer?: string;
  minerals?: string[];
  /** Repair nodes: `recycling`, `refurbishment` or `trade_in_collection`. */
  serviceRole?: string;
  recoveredMetals?: string[];
}

export type Mode = "sea" | "air" | "road" | "rail";

export interface NetworkEdge {
  id: string;
  from: string;
  to: string;
  mode: Mode;
  /** Null when the tier of what it carries is unknown. */
  carriesTier: number | null;
  status: "known" | "inferred";
  sources: Source[];
  via?: [number, number][];
  /** `route` (transport, drawn on the map) or `supply` (who supplies whom). Older files describe the corridor here instead. */
  relation?: string;
  /** `backbone` (reference transport), `supplier_access` (a site's link to its gateway), or another inferred layer. */
  layer?: string;
  /** Name shared by the edges of one lane, for its label. */
  laneName?: string;
  corridor?: string;
  /** Shipping nodes the route passes through (canals, straits). */
  viaNodeIds?: string[];
  /** `return` for reverse logistics (lib/routes.ts isReturn). */
  purpose?: string;
  /** collection, recycling, refurbishment or recovered_material. */
  returnStage?: string;
  contextLayer?: string;
  /** Mineral links and recovered-material routes: the metal carried. */
  metal?: string;
  /** The route this one replaces when used as a detour. */
  alternativeTo?: string;
  basis?: string;
  /** Confidence in an inferred link, shown on hover. */
  confidence?: string;
  confidenceKind?: string;
  /** Part type a supply link carries. */
  partType?: string;
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
  /** Dated reference geography (backbone): when and what it covers. */
  backbone?: { referenceAsOf?: string; scope?: string; routeDefinition?: string };
  snapshotYear: number;
  sampleData: boolean;
  nodes: NetworkNode[];
  edges: NetworkEdge[];
  eventId?: string;
  scope?: string;
  coverage?: { matchedLocations: number; manufacturingLocations: number; unlocatedCompanies?: number; locationCoverage?: string };
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
  predictionScope?: string;
  outcomeObservable?: boolean;
}

/** A prediction for a company whose sites are not disclosed (company-only Supplier Lists). */
export interface CompanyPrediction extends Omit<Prediction, "nodeId"> {
  companyId: string;
  supplier: string;
  ticker: string | null;
  sources: Source[];
  actual: { hit: boolean; car: number } | null;
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
  /** This event's own network file, relative to the data folder. */
  networkPath?: string;
  dateBasis?: string;
  endBasis?: string;
  /** What hit, car, and pHit measure. */
  outcomeDefinition?: string;
  sources?: Source[];
  shock: {
    nodeIds: string[];
    capacityLoss: number | null;
    /** Where the shock happened when it is not a node in the network. */
    location?: { lon: number; lat: number; precision?: string; basis?: string };
    /** A commodity-specific shock (e.g. cobalt): only links carrying this metal pass it on. */
    mineral?: string;
  };
  /** Context-only events have no supplier roster, labels, predictions or metrics. */
  contextOnly?: boolean;
  /** Why the event has no predictions. */
  predictionScope?: string;
  headline: string;
  predictions: Prediction[];
  companyPredictions?: CompanyPrediction[];
  actual: { nodeId: string; hit: boolean; car: number; scope?: string }[];
  options: ScenarioOption[];
  /** Null when the production quota and recovery plan are unknown. */
  quota: {
    weeks: string[];
    target: number[];
    noAction: number[];
    withPlan: number[];
    recoverySentence: string;
    /** The modeled result for each combination of options. */
    optionPlans?: { optionIds: string[]; withPlan: number[] }[];
    /** What the numbers count, e.g. an index where 100 is an assumed weekly reference. */
    unit?: string;
    scope?: string;
    assumption?: boolean;
  } | null;
  money: { coinUsd: number; revenueAtRisk: Range | null; delayedShare: number | null; assumption: boolean };
  /** Things the export states are not known (e.g. "Physical supplier transport routes"). */
  unknowns?: string[];
  affectedRoutes: { blocked: string[]; detour: string[]; expedited: string[] };
  affectedRoutesBasis?: string;
  /** `label` is the plain-language name of the assumption, when the file gives one. */
  sensitivity?: { assumption: string; spearman: number; label?: string }[];
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
  /** baselineAuc is the comparison model; distanceAuc, when present, is distance alone. */
  loeo: { eventId: string; auc: number; brier: number; baselineAuc: number; distanceAuc?: number }[];
  overall: { auc: Range; brier: Range; baselineAuc: Range; distanceAuc?: Range };
  overallPoint?: { auc: number; brier: number; baselineAuc: number; distanceAuc?: number };
  calibration: { binMid: number; observed: number; n: number }[];
  excludedFromMetrics?: { eventId: string; rows: number; hits: number; reason: string }[];
  baselineDefinition?: string;
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
