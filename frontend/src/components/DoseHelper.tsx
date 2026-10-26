import { useMemo, useState } from "react";

/**
 * Turns a dose quoted in the answer into amounts a farmer can measure: per sprayer tank for "per litre" doses, and for the whole parcel
 * for "per hectare" doses. Pure arithmetic on the number the answer already quotes from the TNAU guide; it adds no dose of its own.
 */
const DOSE = /(\d+(?:\.\d+)?)\s*(kg|g|ml|l|litres?|lit)\s*(?:\/|per)\s*(l|lit|litre|litres|ha|hectare)\b/gi;
const TANKS = [10, 15, 16, 20];

const fmt = (n: number, unit: string) => {
  let v = n, u = unit;
  if (u === "g" && v >= 1000) { v /= 1000; u = "kg"; }
  if (u === "ml" && v >= 1000) { v /= 1000; u = "L"; }
  return `${Math.round(v * 100) / 100} ${u}`;
};

export function DoseHelper({ text, areaHa }: { text: string; areaHa?: number | null }) {
  const [tank, setTank] = useState(15);
  const doses = useMemo(() => {
    const seen = new Set<string>();
    const out: { raw: string; value: number; unit: string; per: "l" | "ha" }[] = [];
    for (const m of text.matchAll(DOSE)) {
      const unit = m[2].toLowerCase().startsWith("l") ? "L" : m[2].toLowerCase();
      const per = m[3].toLowerCase().startsWith("h") ? "ha" : "l";
      const key = `${m[1]}${unit}${per}`;
      if (seen.has(key) || (unit === "L" && per === "l")) continue;
      seen.add(key);
      out.push({ raw: m[0].trim(), value: Number(m[1]), unit, per });
    }
    return out.slice(0, 4);
  }, [text]);

  if (!doses.length) return null;
  const hasLitre = doses.some((d) => d.per === "l");
  return (
    <section className="mt-3 rounded-xl border border-border bg-card/60 p-3 text-xs">
      <div className="flex items-center justify-between gap-2">
        <h4 className="font-semibold">Dose at a glance</h4>
        {hasLitre && <label className="flex items-center gap-1.5 text-[10.5px] text-muted-foreground">
          Sprayer tank
          <select value={tank} onChange={(e) => setTank(Number(e.target.value))} className="rounded border border-border bg-background px-1 py-0.5 text-foreground">
            {TANKS.map((t) => <option key={t} value={t}>{t} L</option>)}
          </select>
        </label>}
      </div>
      <ul className="mt-2 space-y-1.5">
        {doses.map((d) => (
          <li key={d.raw} className="flex flex-wrap items-baseline justify-between gap-2 border-b border-border/60 pb-1.5 last:border-0">
            <span className="font-mono text-foreground">{d.raw}</span>
            <span className="text-muted-foreground">
              {d.per === "l"
                ? <>→ <b className="font-medium text-foreground">{fmt(d.value * tank, d.unit)}</b> in a {tank} L tank of water</>
                : areaHa
                  ? <>→ <b className="font-medium text-foreground">{fmt(d.value * areaHa, d.unit)}</b> for this parcel ({areaHa} ha)</>
                  : <>→ per hectare; pick a parcel to see the total for it</>}
            </span>
          </li>
        ))}
      </ul>
      <p className="mt-2 text-[10px] leading-snug text-muted-foreground">Arithmetic only, on the dose quoted above. Check the product is currently registered, read its label, and use protective gear.{hasLitre ? " Water volume per hectare depends on your sprayer." : " Per-hectare amounts of fertilizer or seed are not spray doses."}</p>
    </section>
  );
}
