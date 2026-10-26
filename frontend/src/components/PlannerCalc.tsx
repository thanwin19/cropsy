import { useMemo, useState } from "react";

type Planner = { crop: string; area_acre: number; qty: { expected_low: number; expected_mid: number; expected_high: number } | null; unit: string; price: number | null };

const num = (v: string) => (v.trim() === "" || Number.isNaN(Number(v)) ? 0 : Number(v));
const rs = (n: number) => `Rs ${Math.round(n).toLocaleString("en-IN")}`;

/** Income planner: only arithmetic on the numbers the farmer types. Production and price are pre-filled from the parcel's history and the MSP; costs are never guessed. */
export function PlannerCalc({ plan }: { plan: Planner }) {
  const [qty, setQty] = useState(plan.qty ? String(plan.qty.expected_mid) : "");
  const [price, setPrice] = useState(plan.price != null ? String(plan.price) : "");
  const [acre, setAcre] = useState(String(plan.area_acre));
  const [costs, setCosts] = useState({ seed: "", fertilizer: "", labour: "", sprays: "", water: "", other: "" });
  const r = useMemo(() => {
    const a = num(acre);
    const perAcre = Object.values(costs).reduce((s, v) => s + num(v), 0);
    const revenue = num(qty) * num(price);
    const cost = perAcre * a;
    return { revenue, cost, profit: revenue - cost, breakEven: num(qty) > 0 ? cost / num(qty) : 0, perAcre };
  }, [qty, price, acre, costs]);
  const field = "w-full rounded-md border border-border bg-background px-2 py-1 text-xs";
  const unit = plan.qty ? "quintals" : "units";
  return (
    <div className="mt-2 grid gap-3 text-xs">
      <div className="grid grid-cols-3 gap-2">
        <label className="grid gap-0.5">Area (acre)<input className={field} inputMode="decimal" value={acre} onChange={(e) => setAcre(e.target.value)} /></label>
        <label className="grid gap-0.5">Production ({unit})<input className={field} inputMode="decimal" value={qty} onChange={(e) => setQty(e.target.value)} /></label>
        <label className="grid gap-0.5">Price (Rs per {plan.qty ? "quintal" : "unit"})<input className={field} inputMode="decimal" value={price} onChange={(e) => setPrice(e.target.value)} /></label>
      </div>
      {plan.qty && (
        <div className="flex flex-wrap gap-1.5 text-[10.5px]">
          {(["expected_low", "expected_mid", "expected_high"] as const).map((k) => (
            <button key={k} type="button" onClick={() => setQty(String(plan.qty![k]))} className="rounded-full border border-border bg-muted px-2 py-0.5 hover:bg-accent">
              {k.replace("expected_", "")}: {plan.qty![k]} q
            </button>
          ))}
        </div>
      )}
      <div>
        <p className="mb-1 font-semibold">Your costs per acre (Rs)</p>
        <div className="grid grid-cols-3 gap-2">
          {(Object.keys(costs) as (keyof typeof costs)[]).map((k) => (
            <label key={k} className="grid gap-0.5 capitalize">{k}<input className={field} inputMode="decimal" value={costs[k]} onChange={(e) => setCosts({ ...costs, [k]: e.target.value })} placeholder="0" /></label>
          ))}
        </div>
      </div>
      <dl className="grid grid-cols-2 gap-x-3 gap-y-1 rounded-lg border border-border bg-muted/40 p-2.5">
        <dt className="text-muted-foreground">Income</dt><dd className="text-right font-mono">{rs(r.revenue)}</dd>
        <dt className="text-muted-foreground">Total cost ({rs(r.perAcre)} per acre)</dt><dd className="text-right font-mono">{rs(r.cost)}</dd>
        <dt className="font-semibold">Profit</dt><dd className={`text-right font-mono font-semibold ${r.profit < 0 ? "text-destructive" : "text-success"}`}>{rs(r.profit)}</dd>
        <dt className="text-muted-foreground">Break-even price</dt><dd className="text-right font-mono">{r.breakEven ? `${rs(r.breakEven)} per ${plan.qty ? "quintal" : "unit"}` : "n/a"}</dd>
      </dl>
    </div>
  );
}
