import { useState } from "react";
import { getApiSettings, type Phase7AdvisoryResult } from "@/lib/cropsy-api";

type Baseline = { answer: string; model: string; cost_usd: number; latency_ms: number; uses: string; remaining: number };

/** The calculator's own totals next to the numbers in the answer (same test as verifier check V6). */
export function CrossCheck({ cc }: { cc: NonNullable<Phase7AdvisoryResult["cross_check"]> }) {
  return (
    <section className="mt-3 rounded-xl border border-border bg-card/60 p-3 text-xs" data-testid="cross-check">
      <h4 className="mb-1 font-semibold">🧮 Calculator cross-check {cc.passed ? <span className="text-success">✅ answer matches the calculator</span> : <span className="text-warning">⚠ answer differs from the calculator</span>}</h4>
      <p className="mb-2 text-[10.5px] text-muted-foreground">{cc.note} Parcel area: {cc.area_ha} ha.</p>
      <div className="grid gap-1.5">
        {cc.options.map((o) => (
          <div key={o.recommendation} className={`rounded-lg border px-2.5 py-1.5 ${o.used_in_answer ? "border-success/50 bg-success/5" : "border-border"}`}>
            <b>{o.recommendation}</b> <span className="text-muted-foreground">[{o.source}]</span>
            <div className="font-mono text-[11px]">calculator: N {o.N_kg} kg · P2O5 {o.P2O5_kg} kg · K2O {o.K2O_kg} kg → urea {o.urea_kg} kg, DAP {o.dap_kg} kg, MOP {o.mop_kg} kg {o.used_in_answer ? "· used in the answer ✓" : ""}</div>
          </div>
        ))}
      </div>
    </section>
  );
}

/** Informed (full Cropsy) versus uninformed (one plain model call). On demand only: it costs one small model call. */
export function ComparePlain({ result }: { result: Phase7AdvisoryResult }) {
  const [b, setB] = useState<Baseline | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  async function run() {
    setBusy(true);
    setErr("");
    try {
      const r = await fetch(`${(getApiSettings().baseUrl || "").replace(/\/$/, "")}/api/baseline`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ query: result.query }) });
      const d = await r.json();
      if (!r.ok) throw new Error(d.detail || `error ${r.status}`);
      setB(d);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Could not compare");
    } finally {
      setBusy(false);
    }
  }
  if (!b) {
    return (
      <div className="mt-2">
        <button type="button" onClick={() => void run()} disabled={busy} className="rounded-full border border-border px-3 py-1 text-[10.5px] text-muted-foreground hover:text-foreground disabled:opacity-50" data-testid="compare-plain">
          {busy ? "Asking a plain model…" : "⚖ Compare with a plain model (no tools)"}
        </button>
        {err && <span className="ml-2 text-[10.5px] text-destructive">{err}</span>}
      </div>
    );
  }
  const cost = result.estimated_cost_usd ?? 0;
  const ms = Math.round(result.observability?.latency_ms ?? 0);
  return (
    <section className="mt-3 rounded-xl border border-border bg-card/60 p-3 text-xs" data-testid="compare-panel">
      <h4 className="mb-2 font-semibold">⚖ Same question, two ways</h4>
      <div className="grid gap-2 sm:grid-cols-2">
        <div className="rounded-lg border border-border p-2">
          <b>Plain model alone</b> <span className="text-muted-foreground">({b.model})</span>
          <p className="mt-1 whitespace-pre-wrap">{b.answer}</p>
          <p className="mt-2 font-mono text-[10.5px] text-muted-foreground">No sources · no parcel data · no checks · ${b.cost_usd.toFixed(5)} · {b.latency_ms} ms</p>
        </div>
        <div className="rounded-lg border border-primary/40 bg-primary/5 p-2">
          <b>Cropsy (full pipeline)</b>
          <p className="mt-1 whitespace-pre-wrap">{result.answer}</p>
          <p className="mt-2 font-mono text-[10.5px] text-muted-foreground">
            {result.sources?.length ?? 0} sources · {result.confidence?.label ?? "checked"} · {result.verified ? "verifier passed" : "flagged"} · ${cost.toFixed(5)} · {ms} ms
          </p>
        </div>
      </div>
      <p className="mt-1 text-[10px] text-muted-foreground">The plain model has {b.uses}. Read both and judge the difference yourself.</p>
    </section>
  );
}
