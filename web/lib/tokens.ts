// TypeScript mirror of styles/tokens.css for SVG attributes, which cannot read CSS variables.
// Every value comes from docs/design-spec.md.

export const color = {
  ocean: "#132423",
  land: "#1F3936",
  landStroke: "#2C4C47",
  landHighlight: "#28524B",
  panelBg: "#0E1A19",
  panelBorder: "#27443F",
  textPrimary: "#F1F5F2",
  textBody: "#D5DFDC",
  textSecondary: "#B9C7C3",
  textHeading: "#8FA6A1",
  pillLight: "#E9EEEA",
  pillLightText: "#132423",
  blocked: "#7E8C89",
  moneyIn: "#F2B92B",
  moneyOut: "#5AA0E6",
  /** Red: lost sales and all disruptions. */
  alert: "#D6453D",
} as const;

export const tierColor: Record<number, string> = {
  1: "#C79A6B",
  2: "#E8662F",
  3: "#A98BE8",
  4: "#46C6D8",
  5: "#E9EEEA",
  6: "#7CCB9A",
  7: "#F08CC0",
};

/** Nodes whose production tier the data marks unknown: the panel's neutral heading grey, never a tier color. */
export const tierUnknown = "#8FA6A1";

export function tierColorOf(tier: number | null | undefined): string {
  return (tier != null && tierColor[tier]) || tierUnknown;
}

/** Shipping-node dots are drawn slightly brighter than the tier-5 swatch. */
export const shippingDot = "#F1F5F2";

export const tierLabel: Record<number, string> = {
  1: "Rocks",
  2: "Materials",
  3: "Parts",
  4: "Assembly",
  5: "Shipping",
  6: "Sales",
  7: "Support",
};

export type CoinKind = "gold" | "blue" | "red" | "grey";

export const coin: Record<CoinKind, { fill: string; rim: string; text: string }> = {
  gold: { fill: "#F2B92B", rim: "#9A6A06", text: "#6B4704" },
  blue: { fill: "#5AA0E6", rim: "#1F5E9E", text: "#0E2F52" },
  red: { fill: "#D6453D", rim: "#8E1F19", text: "#FFFFFF" },
  grey: { fill: "#8A9694", rim: "#4E5958", text: "#1D2524" },
};

export const zone = { fill: "rgba(214,69,61,0.22)", border: "#D6453D" };

export const route = {
  seaWidth: 7,
  seaTickWidth: 2,
  seaTickDash: "3 15",
  airDash: "2 7",
  airWidth: 1.6,
  airWidthExpedited: 3,
  detourWidth: 5,
  detourDash: "14 9",
  blockedOpacity: 0.35,
  moneyInWidth: 2.5,
  moneyOutWidth: 3,
};

export const size = {
  mapW: 1440,
  mapH: 810,
  panelW: 400,
  sheetBreakpoint: 900,
  assembly: 26,
  major: 24,
  minor: 16,
  port: 14,
  store: 18,
  carrier: 24,
  hqCardW: 112,
  coin: 24,
  coinLegend: 20,
  delayedOffset: 7,
  shipW: 30,
  shipH: 16,
  quotaBlocks: 20,
};
