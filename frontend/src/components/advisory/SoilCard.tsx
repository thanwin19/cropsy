import React, { useState } from "react";
import { FlaskConical } from "lucide-react";
import type { FieldReport, SoilTestResult } from "@/lib/cropsy-api";
import { Badge, Card, Kv, SourceNote } from "../stitch/ui";

export type SoilValues = { pH: string; EC: string; OC: string; N: string; P: string; K: string };
export const EMPTY_SOIL: SoilValues = { pH: "", EC: "", OC: "", N: "", P: "", K: "" };

const FIELDS: { key: keyof SoilValues; label: string; unit: string; hint: string }[] = [
  { key: "pH", label: "pH", unit: "", hint: "e.g. 6.4" },
  { key: "EC", label: "Salinity (EC)", unit: "dS/m", hint: "e.g. 0.8" },
  { key: "OC", label: "Organic carbon", unit: "%", hint: "e.g. 0.6" },
  { key: "N", label: "Available N", unit: "kg/ha", hint: "e.g. 250" },
  { key: "P", label: "Available P", unit: "kg/ha", hint: "e.g. 18" },
  { key: "K", label: "Available K", unit: "kg/ha", hint: "e.g. 160" },
];
const RATING_TONE = { low: "bad", medium: "warn", high: "ok" } as const;
const RATING_TEXT = { low: "Low", medium: "Medium", high: "High" } as const;

export const SoilCard: React.FC<{
  report: FieldReport; values: SoilValues; onValues: (v: SoilValues) => void; result: SoilTestResult | null; busy: boolean; error: string | null;
  onEvaluate: () => void; onClear: () => void;
}> = ({ report, values, onValues, result, busy, error, onEvaluate, onClear }) => {
  const s = report.soil_panel;
  const [open, setOpen] = useState(false);
  const filled = Object.values(values).some((v) => v !== "");
  return (
    <Card title="Soil management" eyebrow="pH · salinity · nutrients" icon={<FlaskConical size={16} />}
      right={<Badge tone={result ? "ok" : "mute"}>{result ? "your soil test" : "model + sample data"}</Badge>}>
      <div className="grid grid-cols-2 gap-x-6">
        <div>
          <Kv k="pH (record, sample)" v={s.record_ph != null ? `${s.record_ph} · ${s.record_ph_rating?.class ?? ""}` : "n/a"} />
          <Kv k="pH (SoilGrids model)" v={s.soilgrids_ph ?? "n/a"} />
          <Kv k="Organic carbon (model)" v={s.organic_carbon_g_per_kg != null ? `${s.organic_carbon_g_per_kg} g/kg` : "n/a"} />
        </div>
        <div>
          <Kv k="Texture" v={s.texture} />
          <Kv k="Drainage" v={s.drainage.replace(/_/g, " ")} />
          <Kv k="Salinity" v={result?.salinity ? `${result.salinity.value} dS/m · ${result.salinity.class}` : <span className="text-warning">not measured</span>} />
        </div>
      </div>
      {s.record_ph_rating && <p className="text-[11.5px] text-foreground">{s.record_ph_rating.advice}</p>}

      {result && (
        <div className="rounded-xl border border-white/[0.07] bg-black/20 p-3 space-y-2">
          <div className="flex flex-wrap gap-2">
            {(["N", "P", "K", "OC"] as const).filter((k) => result.ratings[k]).map((k) => (
              <Badge key={k} tone={RATING_TONE[result.ratings[k].rating]}>{k === "OC" ? "Organic C" : k} {result.ratings[k].value} · {RATING_TEXT[result.ratings[k].rating]}</Badge>
            ))}
            {result.ph && <Badge tone="info">pH {result.ph.value} · {result.ph.class}</Badge>}
            {result.salinity && <Badge tone={result.salinity.class === "Non-saline" ? "ok" : "warn"}>{result.salinity.class}</Badge>}
          </div>
          {result.ph && <p className="text-[11.5px] text-foreground">{result.ph.advice}</p>}
          <SourceNote>{result.basis}</SourceNote>
        </div>
      )}

      <button onClick={() => setOpen((o) => !o)} className="self-start rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-xs text-primary hover:border-primary/50">
        {open ? "Hide soil-test form" : result ? "Edit my soil test" : "Enter my soil test"}
      </button>
      {open && (
        <div className="space-y-3 rounded-xl border border-white/[0.07] bg-black/20 p-3">
          <p className="text-[11px] text-muted-foreground">Type the numbers from your lab report. Leave blank what you do not have. They stay in this browser only.</p>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
            {FIELDS.map((f) => (
              <label key={f.key} className="flex flex-col gap-1 text-[10.5px] text-muted-foreground">
                {f.label}{f.unit && <span className="text-muted-foreground/60"> ({f.unit})</span>}
                <input inputMode="decimal" value={values[f.key]} placeholder={f.hint} onChange={(e) => onValues({ ...values, [f.key]: e.target.value })}
                  className="rounded-md border border-white/10 bg-black/30 px-2 py-1.5 font-mono text-xs text-white placeholder:text-white/20" />
              </label>
            ))}
          </div>
          <div className="flex items-center gap-2">
            <button onClick={onEvaluate} disabled={!filled || busy} className="rounded-lg bg-primary px-3.5 py-1.5 text-xs font-semibold text-primary-foreground disabled:opacity-40">{busy ? "Rating…" : "Rate my soil"}</button>
            <button onClick={onClear} className="text-xs text-muted-foreground hover:text-white">Clear</button>
            {error && <span className="text-xs text-destructive">{error}</span>}
          </div>
        </div>
      )}
      <SourceNote>{s.basis} {s.salinity.note}</SourceNote>
    </Card>
  );
};

export default SoilCard;
