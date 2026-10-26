import React from "react";
import type { LayerInfo } from "@/lib/cropsy-api";

interface Props {
  layers: Record<string, LayerInfo>;
  value: string;
  onChange: (id: string) => void;
}

/** Layers grouped by the question a farmer actually asks, not by data source. A layer appears under one question only. */
const QUESTIONS: { q: string; hint: string; ids: string[] }[] = [
  { q: "Is my crop healthy?", hint: "Young or thin crop: NDVI or SAVI. Dense mature crop: EVI or NDRE.", ids: ["ndvi", "savi", "evi", "ndre"] },
  { q: "Is it wet or dry?", hint: "Canopy water first (NDMI), then standing water, then how much water the crop is using.", ids: ["ndmi", "ndwi", "et"] },
  { q: "Seeing through cloud", hint: "Radar keeps working in the monsoon when optical satellites see only cloud.", ids: ["rvi", "rsm"] },
  { q: "What is under it?", hint: "The ground itself: what covers it, how fertile the soil is, how high it sits.", ids: ["lulc", "soc", "dem"] },
  { q: "Display and accessibility", hint: "Pictures to orient yourself, and a colour-blind-safe map.", ids: ["tci", "etci", "hybrid", "colorblind"] },
];

const KIND: Record<LayerInfo["kind"], string> = {
  real: "real satellite data",
  modelled: "modelled",
  derived: "our definition",
};

const Tag = ({ children }: { children: React.ReactNode }) => (
  <span className="h-fit whitespace-nowrap rounded border border-border bg-muted px-1.5 py-0.5 font-mono text-[10px] uppercase text-muted-foreground">{children}</span>
);

export const LayerPicker: React.FC<Props> = ({ layers, value, onChange }) => {
  const placed = new Set(QUESTIONS.flatMap((g) => g.ids));
  const extra = Object.keys(layers).filter((id) => !placed.has(id));          // anything new the backend adds still shows up
  const groups = [...QUESTIONS, ...(extra.length ? [{ q: "More layers", hint: "", ids: extra }] : [])];

  return (
    <div className="flex flex-col gap-5" role="radiogroup" aria-label="Map layer">
      <p className="text-sm font-semibold">What do you want to know?</p>

      {groups.map((g) => {
        const items = g.ids.map((id) => layers[id]).filter(Boolean);
        if (!items.length) return null;
        return (
          <fieldset key={g.q}>
            <legend className="mb-1 text-xs text-muted-foreground">{g.q}</legend>
            {g.hint && <p className="mb-2 text-[10px] leading-snug text-muted-foreground/70">{g.hint}</p>}
            <div className="space-y-1">
              {items.map((l) => {
                const on = l.id === value;
                const off = l.months.length === 0;
                return (
                  <button
                    key={l.id}
                    type="button"
                    role="radio"
                    aria-checked={on}
                    disabled={off}
                    onClick={() => onChange(l.id)}
                    title={l.what}
                    className={`grid w-full grid-cols-[20px_minmax(0,1fr)_auto] gap-2 rounded-lg p-2 text-left transition hover:bg-accent disabled:cursor-not-allowed disabled:opacity-40 ${on ? "bg-accent" : ""}`}
                  >
                    <span className={`mt-0.5 grid size-4 place-items-center rounded-full border ${on ? "border-primary" : "border-muted-foreground/50"}`}>
                      {on && <span className="size-2 rounded-full bg-primary" />}
                    </span>
                    <span className="min-w-0">
                      <b className="block text-xs">{l.name}</b>
                      {on ? (
                        <span className="mt-1 flex flex-col gap-1 text-[11px] leading-snug">
                          <span className="text-foreground/90">{l.what}</span>
                          <span className="text-muted-foreground"><b className="font-medium">Use it for: </b>{l.use}</span>
                          <span className="text-warning"><b className="font-medium text-muted-foreground">Limits: </b>{l.caveat}</span>
                        </span>
                      ) : (
                        <small className="block text-[10px] text-muted-foreground">{l.what}</small>
                      )}
                    </span>
                    <Tag>{off ? "no data" : KIND[l.kind]}</Tag>
                  </button>
                );
              })}
            </div>
          </fieldset>
        );
      })}
    </div>
  );
};

export default LayerPicker;
