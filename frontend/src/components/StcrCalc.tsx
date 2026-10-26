import { useEffect, useState } from "react";
import { getApiSettings } from "@/lib/cropsy-api";

type Init = { area_ha: number | null; parcel_id?: string | null; crop?: string | null; example: Record<string, [number, number]> };
type Result = {
  target_q_ha: number;
  nutrients: Record<string, { dose_kg_ha: number }>;
  per_ha_products: Record<string, number>;
  field_products?: Record<string, number>;
  warnings: string[];
  limits: string[];
  method: string;
  example_warning?: string;
};

type Preset = { id: string; label: string; source: string; coefficients: Record<string, number[]> };
const NUTRIENTS = ["N", "P2O5", "K2O"] as const;
const base = () => (getApiSettings().baseUrl || "").replace(/\/$/, "");

/** Soil-test crop-response calculator: F = a x T - b x S. The equation numbers must come from the state / soil-lab STCR table; the worked example is only there to show the arithmetic. */
export function StcrCalc({ init }: { init: Init }) {
  const [target, setTarget] = useState("");
  const [soil, setSoil] = useState<Record<string, string>>({ N: "", P2O5: "", K2O: "" });
  const [coef, setCoef] = useState<Record<string, [string, string]>>({ N: ["", ""], P2O5: ["", ""], K2O: ["", ""] });
  const [area, setArea] = useState(init.area_ha ? String(init.area_ha) : "");
  const [presets, setPresets] = useState<Preset[]>([]);
  const [preset, setPreset] = useState<Preset | null>(null);
  const [organic, setOrganic] = useState<Record<string, string>>({ N: "", P2O5: "", K2O: "" });
  const [res, setRes] = useState<Result | null>(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const input = "w-full rounded border border-border bg-background px-1.5 py-1 font-mono text-xs";

  // published TNAU equations (rice); the farmer still has to confirm the soil series with a soil lab
  useEffect(() => {
    fetch(`${base()}/api/stcr/presets`).then((r) => r.json()).then((d) => setPresets(d.items ?? [])).catch(() => setPresets([]));
  }, []);
  const pickPreset = (id: string) => {
    const pr = presets.find((x) => x.id === id) ?? null;
    setPreset(pr);
    if (pr) setCoef(Object.fromEntries(NUTRIENTS.map((n) => [n, [String(pr.coefficients[n][0]), String(pr.coefficients[n][1])]])) as Record<string, [string, string]>);
  };

  const useExample = () => setCoef(Object.fromEntries(NUTRIENTS.map((n) => [n, [String(init.example[n]?.[0] ?? ""), String(init.example[n]?.[1] ?? "")]])) as Record<string, [string, string]>);

  async function run() {
    setBusy(true); setErr(""); setRes(null);
    try {
      const body = {
        target_q_ha: Number(target),
        soil: Object.fromEntries(NUTRIENTS.map((n) => [n, Number(soil[n])])),
        coefficients: Object.fromEntries(NUTRIENTS.map((n) => [n, preset ? [Number(coef[n][0]), Number(coef[n][1]), preset.coefficients[n][2]] : [Number(coef[n][0]), Number(coef[n][1])]])),
        ...(preset ? { organic_credit: Object.fromEntries(NUTRIENTS.map((n) => [n, Number(organic[n]) || 0])) } : {}),
        ...(area ? { area_ha: Number(area) } : {}),
      };
      const r = await fetch(`${base()}/api/stcr`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
      const j = await r.json();
      if (!r.ok) throw new Error(j.detail || `error ${r.status}`);
      setRes(j);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "calculation failed");
    } finally {
      setBusy(false);
    }
  }

  const ready = target && NUTRIENTS.every((n) => soil[n] !== "" && coef[n][0] !== "" && coef[n][1] !== "");

  return (
    <div className="mt-2 rounded-lg border border-border p-2.5 text-xs" data-testid="stcr-calc">
      <p className="font-semibold">Soil-test fertilizer calculator{init.crop ? ` · ${init.crop}` : ""}{init.parcel_id ? ` · ${init.parcel_id}` : ""}</p>
      <p className="mt-0.5 text-[10.5px] text-muted-foreground">Dose = a × yield target − b × soil-test value, per nutrient. Enter the a and b numbers for your crop and soil from the TNAU or soil-lab table.</p>
      {presets.length > 0 && (
        <label className="mt-2 grid gap-0.5">Published TNAU equation (rice)
          <select className={input} value={preset?.id ?? ""} onChange={(e) => pickPreset(e.target.value)} data-testid="stcr-preset">
            <option value="">Enter my own a and b</option>
            {presets.map((p) => <option key={p.id} value={p.id}>{p.label}</option>)}
          </select>
          {preset && <span className="text-[10px] text-warning">The TNAU page names the soil series, not the district. Confirm your soil series with your soil lab or KVK before using this row.</span>}
        </label>
      )}
      <div className="mt-2 grid grid-cols-[52px_1fr_1fr_1fr] items-center gap-1.5">
        <span />
        <b>a</b><b>b</b><b>soil test (kg/ha)</b>
        {NUTRIENTS.map((n) => (
          <div key={n} className="contents">
            <b>{n}</b>
            <input className={input} inputMode="decimal" aria-label={`${n} a`} value={coef[n][0]} onChange={(e) => setCoef({ ...coef, [n]: [e.target.value, coef[n][1]] })} />
            <input className={input} inputMode="decimal" aria-label={`${n} b`} value={coef[n][1]} onChange={(e) => setCoef({ ...coef, [n]: [coef[n][0], e.target.value] })} />
            <input className={input} inputMode="decimal" aria-label={`${n} soil test`} value={soil[n]} onChange={(e) => setSoil({ ...soil, [n]: e.target.value })} />
          </div>
        ))}
      </div>
      {preset && (
        <div className="mt-2 flex flex-wrap items-center gap-2 text-[10.5px]">Nutrient already supplied by manure or compost (kg/ha, optional):
          {NUTRIENTS.map((n) => <label key={n} className="flex items-center gap-1">{n}<input className={`${input} w-14`} inputMode="decimal" value={organic[n]} onChange={(e) => setOrganic({ ...organic, [n]: e.target.value })} /></label>)}
        </div>
      )}
      <div className="mt-2 flex flex-wrap items-center gap-2">
        <label className="flex items-center gap-1">Yield target (q/ha) <input className={`${input} w-16`} inputMode="decimal" value={target} onChange={(e) => setTarget(e.target.value)} /></label>
        <label className="flex items-center gap-1">Area (ha) <input className={`${input} w-16`} inputMode="decimal" value={area} onChange={(e) => setArea(e.target.value)} /></label>
        <button type="button" onClick={useExample} className="rounded-full border border-border px-2 py-1 text-[10.5px]">Fill the worked example's a and b</button>
        <button type="button" onClick={() => void run()} disabled={!ready || busy} className="rounded-lg bg-primary px-3 py-1.5 font-semibold text-primary-foreground disabled:opacity-50">Calculate</button>
      </div>
      {err && <p className="mt-1.5 text-destructive">{err}</p>}
      {res && (
        <div className="mt-2 rounded bg-muted/40 p-2">
          {res.example_warning && <p className="mb-1 text-warning">Worked example only: it applies to {res.example_warning}. Do not use it as a recommendation.</p>}
          <p className="font-semibold">Nutrient dose (kg/ha): {NUTRIENTS.map((n) => `${n} ${res.nutrients[n].dose_kg_ha}`).join(" · ")}</p>
          <p className="mt-1">Per hectare: {Object.entries(res.per_ha_products).map(([k, v]) => `${k} ${v} kg`).join(" · ")}</p>
          {res.field_products && <p>Your field: {Object.entries(res.field_products).map(([k, v]) => `${k} ${v} kg`).join(" · ")}</p>}
          {res.warnings.map((w) => <p key={w} className="text-warning">{w}</p>)}
          <p className="mt-1 text-[10px] text-muted-foreground">{res.method}</p>
          {res.limits.map((l) => <p key={l} className="text-[10px] text-muted-foreground">{l}</p>)}
        </div>
      )}
    </div>
  );
}
