// Small original glyphs: node symbols, label pills, coins, ships.
// Sizes and colors follow docs/design-spec.md; markup follows design/reference/*.html.

import type { CSSProperties, ReactNode } from "react";
import { coin as coinColors, color, shippingDot, tierColor, tierColorOf, type CoinKind } from "@/lib/tokens";
import type { NodeKind } from "@/lib/types";

const HEX = "M13 1 L24 7 L24 19 L13 25 L2 19 L2 7 Z";
const FACTORY = "M8 17 V11 L11 13 V11 L14 13 V11 L18 13 V17 Z";
const TRIANGLE = "M12 2 L23 21 L1 21 Z";

/** A node's symbol, `size` px square, drawn at the origin of its box. */
/** Mining region: a soft sandstone glow (the place is a region, not an exact point) around a faceted ore stone. */
function MineSymbol({ c, size }: { c: string; size: number }) {
  const id = `mine-glow-${c.slice(1)}`;
  return (
    <svg width={size} height={size} viewBox="0 0 40 40" aria-hidden="true">
      <defs>
        <radialGradient id={id}>
          <stop offset="0%" stopColor={c} stopOpacity={0.75} />
          <stop offset="70%" stopColor={c} stopOpacity={0.32} />
          <stop offset="100%" stopColor={c} stopOpacity={0} />
        </radialGradient>
      </defs>
      <circle cx="20" cy="20" r="20" fill={`url(#${id})`} />
      <path d={ORE} fill={c} stroke={color.ocean} strokeWidth={1.2} strokeLinejoin="round" />
      <path d="M15.5 19 L20 16.5 L24.5 19 M20 16.5 L20 24" fill="none" stroke={color.ocean} strokeWidth={1} strokeLinejoin="round" opacity={0.6} />
    </svg>
  );
}

/** Refinery: a squat process tank with two stacks. */
function RefinerySymbol({ c, size }: { c: string; size: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true">
      <rect x="5" y="3" width="3.5" height="9" rx="1" fill={c} />
      <rect x="14" y="6" width="3.5" height="6" rx="1" fill={c} />
      <rect x="2.5" y="10" width="19" height="11" rx="3" fill={c} stroke={color.ocean} strokeWidth={1} />
      <path d="M5 15.5 H19" stroke={color.ocean} strokeWidth={1.6} strokeLinecap="round" />
    </svg>
  );
}

/** Repair and recycling: a tier-7 disc with a looping arrow (goods coming back). */
function RepairSymbol({ c, size }: { c: string; size: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="12" cy="12" r="10.5" fill={c} stroke={color.ocean} strokeWidth={1.5} />
      <path d="M16.6 9.2 A5.4 5.4 0 1 0 17.2 13.6" fill="none" stroke={color.ocean} strokeWidth={2} strokeLinecap="round" />
      <path d="M17.8 5.8 L17 9.8 L13.1 8.9" fill="none" stroke={color.ocean} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

/** Mines are tier 1, refineries tier 2 and repair sites tier 7 even when the file leaves the tier blank. */
const kindTier = (kind: NodeKind, tier: number | null) => tier ?? (kind === "mine" ? 1 : kind === "refinery" ? 2 : kind === "repair" ? 7 : null);

/** `fill` overrides the tier color (e.g. predicted risk during a disruption). */
export function NodeSymbol({ kind, tier, size, fill }: { kind: NodeKind; tier: number | null; size: number; fill?: string }) {
  const c = fill ?? tierColorOf(kindTier(kind, tier));
  switch (kind) {
    case "mine":
      return <MineSymbol c={c} size={size} />;
    case "refinery":
      return <RefinerySymbol c={c} size={size} />;
    case "repair":
      return <RepairSymbol c={c} size={size} />;
    case "assembly":
      return (
        <svg width={size} height={size} viewBox="0 0 26 26" aria-hidden="true">
          <path d={HEX} fill={c} stroke={color.ocean} strokeWidth={2} />
          <path d={FACTORY} fill={color.ocean} />
        </svg>
      );
    case "supplier_major":
      return (
        <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true">
          <path d={TRIANGLE} fill={c} stroke={c} strokeWidth={1} strokeLinejoin="round" />
        </svg>
      );
    case "supplier_minor":
      return (
        <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true">
          <path d={TRIANGLE} fill="none" stroke={c} strokeWidth={2} strokeLinejoin="round" />
        </svg>
      );
    case "sales_region":
      // One of Apple's reporting regions (not a store): the sales color, whatever the tier.
      return <div style={{ width: size, height: size, background: tierColor[6], border: `3px solid ${tierColor[6]}`, borderRadius: 3 }} />;
    case "event_anchor":
      return <div style={{ width: size, height: size, borderRadius: "50%", background: color.alert, border: `3px solid ${color.ocean}` }} />;
    case "port":
    case "airport":
    case "canal":
    case "chokepoint":
    case "border":
      return <div style={{ width: size, height: size, borderRadius: "50%", background: shippingDot, border: `3px solid ${color.ocean}` }} />;
    case "carrier":
      return (
        <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true">
          <circle cx="12" cy="15" r="5" fill={c} />
          <path d="M5 9 A9 9 0 0 1 19 9" fill="none" stroke={c} strokeWidth={2} strokeLinecap="round" />
          <path d="M2 5.5 A13 13 0 0 1 22 5.5" fill="none" stroke={c} strokeWidth={2} strokeLinecap="round" />
        </svg>
      );
    case "retailer":
      return <div style={{ width: size, height: size, background: color.ocean, border: `3px solid ${c}`, borderRadius: 3 }} />;
    default:
      // apple_store: filled square with radius 3.
      return <div style={{ width: size, height: size, background: c, border: `3px solid ${c}`, borderRadius: 3 }} />;
  }
}

/** Legend versions of the symbols (18 px, as in the panel map key). */
export function KeySymbol({ kind }: { kind: "assembly" | "major" | "minor" | "port" | "store" | "retailer" | "carrier" | "mine" | "refinery" | "repair" | "return" }) {
  const box = (child: ReactNode) => (
    <div style={{ width: 18, height: 18, display: "flex", alignItems: "center", justifyContent: "center", flex: "none" }}>{child}</div>
  );
  switch (kind) {
    case "assembly":
      return box(
        <svg width="18" height="18" viewBox="0 0 26 26" aria-hidden="true">
          <path d={HEX} fill={tierColor[4]} />
        </svg>,
      );
    case "major":
      return box(
        <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true">
          <path d={TRIANGLE} fill={tierColor[3]} />
        </svg>,
      );
    case "minor":
      return box(
        <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true">
          <path d="M12 3 L22 20 L2 20 Z" fill="none" stroke={tierColor[3]} strokeWidth={2.5} strokeLinejoin="round" />
        </svg>,
      );
    case "mine":
      return box(<MineSymbol c={tierColor[1]} size={26} />);
    case "refinery":
      return box(<RefinerySymbol c={tierColor[2]} size={18} />);
    case "repair":
      return box(<RepairSymbol c={tierColor[7]} size={18} />);
    case "return":
      return box(
        <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true">
          <path d="M1 9 H17" stroke={tierColor[7]} strokeWidth={2.5} strokeDasharray="4 3" strokeLinecap="round" />
        </svg>,
      );
    case "port":
      return box(<div style={{ width: 12, height: 12, borderRadius: "50%", background: shippingDot, margin: 3 }} />);
    case "store":
      return box(<div style={{ width: 14, height: 14, background: tierColor[6], borderRadius: 3, margin: 2 }} />);
    case "retailer":
      return box(<div style={{ width: 14, height: 14, border: `3px solid ${tierColor[6]}`, borderRadius: 3, margin: 2 }} />);
    case "carrier":
      return box(
        <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true">
          <circle cx="12" cy="15" r="5" fill={tierColor[6]} />
          <path d="M5 9 A9 9 0 0 1 19 9" fill="none" stroke={tierColor[6]} strokeWidth={2.5} strokeLinecap="round" />
        </svg>,
      );
  }
}

export function Pill({
  children,
  big = false,
  bg = color.pillLight,
  fg = color.pillLightText,
  style,
  className,
  ...data
}: {
  children: ReactNode;
  big?: boolean;
  bg?: string;
  fg?: string;
  style?: CSSProperties;
  className?: string;
  [data: `data-${string}`]: string;
}) {
  return (
    <div className={`${big ? "pill pill-lg" : "pill pill-sm"}${className ? ` ${className}` : ""}`} style={{ background: bg, color: fg, ...style }} {...data}>
      {children}
    </div>
  );
}

/** A faceted ore stone, centered in a 40 × 40 box. */
const ORE = "M14 22 L15.5 17.5 L20 15 L24.5 17.5 L26 22 L22.5 25.5 L17.5 25.5 Z";

const CRACK = "M13 1 L10 9 L14 12 L9 23";

/** Arcade coin with a "$"; red coins carry a crack line. */
export function Coin({ kind, size, style }: { kind: CoinKind; size: number; style?: CSSProperties }) {
  const c = coinColors[kind];
  return (
    <div
      className="coin"
      style={{
        width: size,
        height: size,
        background: c.fill,
        border: `2px solid ${c.rim}`,
        boxShadow: `inset 0 -3px 0 ${c.rim}`,
        color: c.text,
        fontSize: Math.round(size / 2),
        ...style,
      }}
    >
      $
      {kind === "red" && (
        <svg width="100%" height="100%" viewBox="0 0 24 24" aria-hidden="true" style={{ position: "absolute", left: 0, top: 0 }}>
          <path d={CRACK} fill="none" stroke={color.ocean} strokeWidth={2.2} strokeLinejoin="round" />
        </svg>
      )}
    </div>
  );
}

/** Original container ship: white hull, two tier-4 containers, a bridge. */
export function Ship({ style }: { style?: CSSProperties }) {
  return (
    <div className="ship" style={{ position: "relative", ...style }}>
      <svg width="30" height="16" viewBox="0 0 30 16" aria-hidden="true">
        <path d="M1 8 H29 L25 15 H5 Z" fill={color.textPrimary} />
        <rect x="6" y="3" width="5" height="5" fill={tierColor[4]} />
        <rect x="12" y="3" width="5" height="5" fill={tierColor[4]} />
        <rect x="18" y="1" width="5" height="7" fill={color.textPrimary} />
      </svg>
    </div>
  );
}
