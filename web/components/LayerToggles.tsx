"use client";

export interface Layers {
  sea: boolean;
  air: boolean;
  /** Off: road links show only for the selected or hovered node, or zoomed into a country. On: all of them. */
  road: boolean;
  suppliers: boolean;
  money: boolean;
  /** Return routes and the repair and recycling sites they reach. */
  returns: boolean;
}

export const DEFAULT_LAYERS: Layers = { sea: true, air: true, road: false, suppliers: true, money: true, returns: false };

const ITEMS: { key: keyof Layers; label: string }[] = [
  { key: "sea", label: "Sea lanes" },
  { key: "air", label: "Air routes" },
  { key: "road", label: "Road links" },
  { key: "suppliers", label: "Suppliers" },
  { key: "money", label: "Money" },
  { key: "returns", label: "Returns" },
];

/** Switches for what the map draws. */
export default function LayerToggles({ layers, onChange }: { layers: Layers; onChange: (next: Layers) => void }) {
  return (
    <section>
      <h2 className="panel-heading">LAYERS</h2>
      <div className="layer-toggles" role="group" aria-label="Map layers">
        {ITEMS.map(({ key, label }) => (
          <label key={key} className="layer-toggle">
            <input type="checkbox" checked={layers[key]} onChange={() => onChange({ ...layers, [key]: !layers[key] })} data-layer-toggle={key} />
            {label}
          </label>
        ))}
      </div>
      {!layers.road && <div className="panel-tiny">Road links show for the selected or hovered site, or when zoomed into a country.</div>}
    </section>
  );
}
