import React, { useState } from "react";
import { Leaf } from "lucide-react";
import type { FieldReport, SoilTestResult } from "@/lib/cropsy-api";
import { Badge, Card, SourceNote } from "../stitch/ui";
import type { AreaUnit } from "./HealthCard";

const ACRE_PER_HA = 0.404686;                 // 1 acre = 0.4047 ha, so kg/ha x 0.4047 = kg/acre
const RATING_TONE = { low: "bad", medium: "warn", high: "ok" } as const;
const RATING_WORD = { low: "Low", medium: "Medium", high: "High" } as const;

export const FertilizerCard: React.FC<{ report: FieldReport; soil: SoilTestResult | null; unit: AreaUnit }> = ({ report, soil, unit }) => {
  const f = report.fertilizer;
  const [idx, setIdx] = useState(0);
  const opt = f.options[Math.min(idx, f.options.length - 1)];
  const adj = soil?.adjusted_fertilizer?.find((a) => a.recommendation === opt?.recommendation) ?? null;
  const shown = adj ?? opt;
  const k = unit === "acre" ? ACRE_PER_HA : 1;
  const per = (n: number) => (n / f.area_ha) * k;                   // kg per ha (or per acre) from the parcel total
  const counts = soil?.counts;

  const rows = shown ? [
    { nutrient: "Nitrogen (N)", key: "N" as const, total: shown.N_kg, product: "Urea", pkg: shown.urea_kg, note: "46% N, after crediting the N in DAP" },
    { nutrient: "Phosphorus (P₂O₅)", key: "P" as const, total: shown.P2O5_kg, product: "DAP", pkg: shown.dap_kg, note: "18-46-0" },
    { nutrient: "Potassium (K₂O)", key: "K" as const, total: shown.K2O_kg, product: "MOP", pkg: shown.mop_kg, note: "muriate of potash, 60% K₂O" },
  ] : [];

  return (
    <Card title="Fertiliser" eyebrow="N · P · K against the TNAU target" icon={<Leaf size={16} />}
      right={<Badge tone={soil ? "ok" : "mute"}>{soil ? "adjusted to your soil test" : "standard dose"}</Badge>}>
      <div className="grid grid-cols-3 gap-2 text-center">
        {[["Need attention", counts?.needs_attention, "text-destructive"], ["Monitor closely", counts?.monitor, "text-warning"], ["Optimal", counts?.optimal, "text-primary"]].map(([label, n, tone]) => (
          <div key={label as string} className="rounded-xl border border-white/[0.06] bg-white/[0.03] py-2">
            <div className={`font-serif text-2xl ${tone}`}>{counts ? (n as number) : "–"}</div>
            <div className="font-mono text-[9.5px] uppercase text-muted-foreground/70">{label as string}</div>
          </div>
        ))}
      </div>
      {!soil && <p className="text-[11.5px] text-muted-foreground">No soil test entered yet, so the nutrient status above is blank and the standard TNAU dose is shown. Enter your lab numbers in the Soil card to rate each nutrient and adjust the dose.</p>}

      {f.options.length === 0 ? (
        <p className="text-xs text-muted-foreground">{f.note}</p>
      ) : (
        <>
          <label className="flex flex-col gap-1 text-[11px] text-muted-foreground">
            TNAU recommendation (they differ by variety duration, season and soil)
            <select value={idx} onChange={(e) => setIdx(Number(e.target.value))} className="rounded-lg border border-white/10 bg-black/30 px-2 py-1.5 font-mono text-xs text-white">
              {f.options.map((o, i) => <option key={o.recommendation} value={i}>{o.recommendation} · {o.source.replace("Crop Production Guide: ", "").replace(" 2020", "")}</option>)}
            </select>
          </label>

          <div className="overflow-x-auto">
            <table className="w-full min-w-[460px] text-[11.5px]">
              <thead>
                <tr className="border-b border-white/10 text-left font-mono text-[9.5px] uppercase text-muted-foreground/70">
                  <th className="py-1.5 pr-2">Nutrient</th><th className="pr-2 text-right">Target / {unit === "acre" ? "acre" : "ha"}</th><th className="pr-2 text-right">Whole parcel</th><th className="pr-2">Product</th><th className="text-right">Quantity</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => {
                  const rating = soil?.ratings[r.key];
                  return (
                    <tr key={r.key} className="border-b border-white/[0.05] align-top">
                      <td className="py-2 pr-2">
                        <div className="text-foreground">{r.nutrient}</div>
                        {rating && <Badge tone={RATING_TONE[rating.rating]}>{RATING_WORD[rating.rating]} in soil · ×{soil!.adjustment[r.key]}</Badge>}
                      </td>
                      <td className="pr-2 text-right font-mono text-white">{per(r.total).toFixed(1)} kg</td>
                      <td className="pr-2 text-right font-mono text-foreground">{r.total.toLocaleString()} kg</td>
                      <td className="pr-2"><div className="text-foreground">{r.product}</div><div className="text-[10px] text-muted-foreground/70">{r.note}</div></td>
                      <td className="text-right font-mono text-white">{r.pkg.toLocaleString()} kg</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <p className="text-[10.5px] text-muted-foreground/70">For {f.area_ha} ha. {f.assumptions}. Quantities are whole kilograms.</p>
        </>
      )}

      <div className="rounded-xl border border-white/[0.06] bg-black/20 p-3">
        <div className="mb-1.5 font-mono text-[9.5px] uppercase tracking-wider text-primary">Organic alternatives (quoted from the guide)</div>
        {f.organic.length === 0 ? <p className="text-[11px] text-muted-foreground/60">No curated organic option for this crop.</p> : (
          <ul className="space-y-1.5">
            {f.organic.map((o, i) => (
              <li key={i} className="text-[11.5px] leading-relaxed text-foreground/90">{o.text} <span className="whitespace-nowrap font-mono text-[10px] text-muted-foreground/70">{o.source.replace("Crop Production Guide: ", "").replace(" 2020", "")}</span></li>
            ))}
          </ul>
        )}
      </div>
      <SourceNote>{f.note} {soil?.basis}</SourceNote>
    </Card>
  );
};

export default FertilizerCard;
