"use client";

import { useEffect, useRef } from "react";
import type { Chute as ChuteData, Stack } from "@/lib/stack";
import { color, tierColorOf } from "@/lib/tokens";
import { NodeSymbol } from "./Glyphs";

/** Original chute: a rounded tube with chevrons that slide in the direction of flow. */
function Chute({ chute }: { chute: ChuteData }) {
  const up = chute.direction === "up";
  const tint = !chute.active ? color.panelBorder : up ? color.alert : color.textSecondary;
  const label = up ? "Shortage" : "Cancelled orders";
  const chevron = up ? "M4 10 L11 4 L18 10" : "M4 4 L11 10 L18 4";
  return (
    <div className={`chute chute-${chute.direction}${chute.active ? " active" : ""}`} data-chute={`${chute.gap}-${chute.direction}`} data-active={String(chute.active)}>
      <svg width="22" height="44" viewBox="0 0 22 44" aria-hidden="true">
        <rect x="1" y="1" width="20" height="42" rx="10" fill="none" stroke={tint} strokeWidth="2" />
        <clipPath id={`chute-clip-${chute.gap}-${chute.direction}`}>
          <rect x="3" y="3" width="16" height="38" rx="8" />
        </clipPath>
        <g clipPath={`url(#chute-clip-${chute.gap}-${chute.direction})`}>
          <g className="chute-chevrons">
            {[-14, 0, 14, 28, 42].map((y) => (
              <path key={y} d={chevron} transform={`translate(0 ${y + 4})`} fill="none" stroke={tint} strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" />
            ))}
          </g>
        </g>
      </svg>
      <span className="chute-label" style={{ color: chute.active ? tint : undefined }}>
        {up ? "▲" : "▼"} {label}
      </span>
    </div>
  );
}

interface Props {
  stack: Stack;
  onClose: () => void;
  onSelectNode: (id: string) => void;
}

/** Stacked tier panels for one assembly factory, with chutes between them. */
export default function StackOverlay({ stack, onClose, onSelectNode }: Props) {
  const closeRef = useRef<HTMLButtonElement>(null);
  useEffect(() => closeRef.current?.focus(), [stack.factory.id]);

  return (
    <div className="stack-overlay" role="dialog" aria-label={`Supplier stack for ${stack.factory.name}`}>
      <div className="stack-head">
        <div>
          <div className="panel-heading" style={{ margin: 0 }}>
            SUPPLIER STACK
          </div>
          <div className="stack-title">{stack.factory.name}</div>
        </div>
        <button ref={closeRef} type="button" className="text-button" onClick={onClose}>
          Close
        </button>
      </div>

      {stack.levels.map((level, i) => (
        <div key={level.key}>
          {i > 0 && (
            <div className="chute-row">
              {stack.chutes
                .filter((c) => c.gap === i - 1)
                .map((c) => (
                  <Chute key={c.direction} chute={c} />
                ))}
            </div>
          )}
          <div className={level.partial ? "stack-level partial" : "stack-level"} data-level={level.key}>
            <div className="stack-level-title">{level.title}</div>
            {level.groups.length === 0 ? (
              <div className="panel-note">No supplier links in the data at this level.</div>
            ) : (
              level.groups.map((g) => (
                <div key={g.partType} className="stack-group">
                  <div className="stack-group-title">{g.partType}</div>
                  <div className="stack-tiles">
                    {g.nodes.map((n) => (
                      <button
                        key={n.id}
                        type="button"
                        className={stack.hit.has(n.id) ? "stack-tile hit" : "stack-tile"}
                        style={{ borderColor: tierColorOf(n.tier) }}
                        onClick={() => onSelectNode(n.id)}
                        data-tile={n.id}
                      >
                        <NodeSymbol kind={n.kind} tier={n.tier} size={16} />
                        <span>
                          <span className="stack-tile-name">{n.name}</span>
                          <span className="stack-tile-region">{n.region}</span>
                        </span>
                      </button>
                    ))}
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      ))}
      <div className="panel-tiny">
        Links come from the network file; tier 2 is only partly known from public sources. Chutes light up when the scenario predicts a hit.
      </div>
    </div>
  );
}
