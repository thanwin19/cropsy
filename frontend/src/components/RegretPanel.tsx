import { useEffect, useMemo, useRef, useState } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { getApiSettings, type RegretResult } from "@/lib/cropsy-api";
import { VILLAGE_PARCELS } from "@/data/villageParcels.generated";

const base = () => (getApiSettings().baseUrl || "").replace(/\/$/, "");
const ACT_COLOR: Record<string, string> = { "ACT NOW": "#ef4444", PREPARE: "#f59e0b", MONITOR: "#6b7280" };
type Src = { parcel_id: string; issue: string; neighbours_in_reach: number };
type Brief = { tamil: string; english: string; model: string; cost_usd: number; latency_ms: number; note?: string; cached?: boolean };

const n = (v: string) => (v.trim() === "" || Number.isNaN(Number(v)) ? 0 : Number(v));
const rs = (x: number) => `Rs ${Math.round(x).toLocaleString("en-IN")}`;
const hm = (sec: number) => {
  const s = Math.max(0, Math.floor(sec));
  return `${Math.floor(s / 3600)}h ${String(Math.floor((s % 3600) / 60)).padStart(2, "0")}m ${String(s % 60).padStart(2, "0")}s`;
};

/** Counterfactual regret: the weather timeline with the likely infection window, the cost of the missed prevention moment, and which parcels are in the same position now. */
export function RegretPanel({ initial, sources }: { initial: RegretResult; sources: Src[] }) {
  const [res, setRes] = useState<RegretResult>(initial);
  const [src, setSrc] = useState(initial.source.parcel_id);
  const [p, setP] = useState({ rh: String(initial.params?.rh_min ?? ""), tlo: String(initial.params?.t_low ?? ""), thi: String(initial.params?.t_high ?? ""), mh: String(initial.params?.min_hours ?? ""), l0: String(initial.params?.latency_min ?? ""), l1: String(initial.params?.latency_max ?? "") });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [brief, setBrief] = useState<Brief | null>(null);
  const [briefBusy, setBriefBusy] = useState(false);
  const [loss, setLoss] = useState(String(initial.economics?.default_loss_pct ?? 15));
  const [yieldT, setYieldT] = useState(String(initial.economics?.yield_mid_t_ha ?? ""));
  const [price, setPrice] = useState(String(initial.economics?.price_per_quintal ?? ""));
  const [cost, setCost] = useState("");
  const [t0, setT0] = useState(Date.now());
  const [tick, setTick] = useState(0);
  const div = useRef<HTMLDivElement>(null);
  const map = useRef<L.Map | null>(null);
  const layer = useRef<L.LayerGroup | null>(null);

  useEffect(() => {
    const id = setInterval(() => setTick((x) => x + 1), 1000);
    return () => clearInterval(id);
  }, []);
  void tick;
  const elapsed = (Date.now() - t0) / 1000;

  const body = (parcel = src) => ({ source_parcel: parcel, rh_min: p.rh, t_low: p.tlo, t_high: p.thi, min_hours: p.mh, latency_min: p.l0, latency_max: p.l1 });

  async function run(parcel = src, params = true) {
    setBusy(true);
    setErr("");
    setBrief(null);
    try {
      const r = await fetch(`${base()}/api/regret`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(params ? body(parcel) : { source_parcel: parcel }) });
      const d = await r.json();
      if (!r.ok) throw new Error(d.detail || `error ${r.status}`);
      setRes(d);
      setT0(Date.now());
      if (!params && d.params) setP({ rh: String(d.params.rh_min), tlo: String(d.params.t_low), thi: String(d.params.t_high), mh: String(d.params.min_hours), l0: String(d.params.latency_min), l1: String(d.params.latency_max) });
      if (d.economics) {
        setLoss(String(d.economics.default_loss_pct));
        setYieldT(String(d.economics.yield_mid_t_ha ?? ""));
        setPrice(String(d.economics.price_per_quintal ?? ""));
      }
    } catch (e) {
      setErr(e instanceof Error ? e.message : "analysis failed");
    } finally {
      setBusy(false);
    }
  }

  async function makeBrief() {
    setBriefBusy(true);
    setErr("");
    try {
      const r = await fetch(`${base()}/api/regret/brief`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body(res.source.parcel_id)) });
      const d = await r.json();
      if (!r.ok) throw new Error(d.detail || `error ${r.status}`);
      setBrief(d);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "brief failed");
    } finally {
      setBriefBusy(false);
    }
  }

  // map of every parcel coloured by today's action
  useEffect(() => {
    if (!div.current || map.current) return;
    const m = L.map(div.current, { zoomControl: true, scrollWheelZoom: false });
    L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}", { maxNativeZoom: 17, maxZoom: 18, attribution: "Esri World Imagery" }).addTo(m);
    map.current = m;
    layer.current = L.layerGroup().addTo(m);
    m.fitBounds(L.latLngBounds(VILLAGE_PARCELS.flatMap((x) => x.coords)).pad(0.05));
    setTimeout(() => m.invalidateSize(), 200);
    return () => {
      m.remove();
      map.current = null;
    };
  }, []);
  useEffect(() => {
    const g = layer.current;
    if (!g || !res.available) return;
    g.clearLayers();
    const by = new Map(res.twins.map((t) => [t.parcel_id, t]));
    VILLAGE_PARCELS.forEach((v) => {
      const isSrc = v.id === res.source.parcel_id;
      const t = by.get(v.id);
      const color = isSrc ? "#a855f7" : t ? ACT_COLOR[t.act] : "#374151";
      const hot = t && t.act !== "MONITOR";
      L.polygon(v.coords, { color, weight: isSrc || hot ? 3 : 1, fillColor: color, fillOpacity: isSrc ? 0.55 : t ? (hot ? 0.5 : 0.25) : 0.06 })
        .bindTooltip(isSrc ? `${v.id}: infected (recorded)` : t ? `${v.id} · ${t.stage}: ${t.act}${t.hours_to_open != null ? ` · window opens in ~${t.hours_to_open} h` : ""}` : `${v.id}: other crop`, { sticky: true })
        .addTo(g);
    });
    const pts = VILLAGE_PARCELS.filter((v) => v.id === res.source.parcel_id || by.has(v.id)).flatMap((v) => v.coords);
    if (pts.length && map.current) map.current.fitBounds(L.latLngBounds(pts).pad(0.1), { maxZoom: 15 });
  }, [res]);

  // loss and regret from the editable inputs
  const econ = useMemo(() => {
    const e = res.economics;
    if (!e) return null;
    const tons = n(yieldT) * e.area_ha;
    const value = tons * 10 * n(price);
    const lossRs = value * (n(loss) / 100);
    const c = cost.trim() === "" ? null : n(cost);
    return { tons, value, lossRs, regret: c == null ? null : lossRs - c };
  }, [res, yieldT, price, loss, cost]);

  if (!res.available) return <p className="mt-2 text-xs text-muted-foreground">{res.message}</p>;
  const s = res.history.series;
  const N = s.time.length;
  const W = 1000, H = 120;
  const x = (i: number) => (i / N) * W;
  const rc = res.reconstruction;
  const idx = (iso: string) => Math.max(0, Math.min(N, s.time.findIndex((t) => t >= iso)));
  const iFrom = idx(rc.expected_infection_from), iTo = idx(rc.expected_infection_to);
  const days = Array.from({ length: Math.floor(N / 72) }, (_, k) => k * 72);
  const field = "w-full rounded-md border border-border bg-background px-2 py-1";

  return (
    <div className="mt-2 grid gap-3 text-xs" data-testid="regret-panel">
      <div className="rounded-lg border border-border bg-muted/30 p-2.5">
        <p className="mb-1 font-semibold">Weather timeline: {res.source.disease} on {res.source.parcel_id} <span className="font-normal text-muted-foreground">(green = hours that suit the disease)</span></p>
        <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label="Hourly weather suitability for the last three weeks and the next three days">
          <rect x={x(iFrom)} y="6" width={Math.max(2, x(iTo) - x(iFrom))} height={H - 28} fill="#38bdf8" opacity="0.18" />
          {s.fav.map((f, i) => (f ? <rect key={i} x={x(i)} y="10" width={Math.max(1, W / N)} height={H - 36} fill={i > s.now_i ? "#f59e0b" : "#22c55e"} /> : <rect key={i} x={x(i)} y={H - 34} width={Math.max(1, W / N)} height="8" fill="#374151" />))}
          {rc.best && <rect x={x(idx(rc.best.start))} y="6" width={Math.max(3, x(idx(rc.best.end)) - x(idx(rc.best.start)))} height={H - 28} fill="none" stroke="#fff" strokeWidth="2.5" strokeDasharray="5 3" />}
          <line x1={x(s.now_i)} x2={x(s.now_i)} y1="2" y2={H - 16} stroke="#fff" strokeWidth="2" />
          <text x={x(s.now_i) + 4} y="12" fill="#fff" fontSize="11">now</text>
          {days.map((i) => <text key={i} x={x(i) + 2} y={H - 4} fill="#9ca3af" fontSize="10">{s.time[i]?.slice(5, 10)}</text>)}
        </svg>
        <div className="mt-1 flex flex-wrap gap-2 text-[10px] text-muted-foreground">
          <span><span className="text-[#22c55e]">■</span> suitable hours (past)</span><span><span className="text-[#f59e0b]">■</span> suitable hours (forecast)</span>
          <span><span className="text-[#38bdf8]">■</span> expected infection period</span><span>▭ most plausible window</span><span>| now</span>
        </div>
      </div>

      <div className="rounded-lg border border-border p-2.5" data-testid="regret-statement">
        <p className="font-semibold">When did this become possible?</p>
        <p className="mt-1">{rc.statement}</p>
        <p className="mt-1 text-[10.5px] text-muted-foreground">Symptoms noted {rc.symptom_noted_days_ago} days ago (dummy record). {rc.candidates.length} suitable window(s) fell in the expected infection period.</p>
      </div>

      <div className="rounded-lg border border-border bg-muted/30 p-2.5">
        <p className="mb-1 font-semibold">Change the assumptions: the dates and the list below change at once</p>
        <div className="grid grid-cols-3 gap-2 sm:grid-cols-6">
          {([["Humidity at least %", "rh"], ["Temp from C", "tlo"], ["Temp to C", "thi"], ["Hours in a row", "mh"], ["Latency min days", "l0"], ["Latency max days", "l1"]] as const).map(([label, k]) => (
            <label key={k} className="grid gap-0.5 text-[10.5px]">{label}<input className={field} inputMode="decimal" value={p[k]} onChange={(e) => setP({ ...p, [k]: e.target.value })} /></label>
          ))}
        </div>
        <div className="mt-2 flex flex-wrap items-end gap-2">
          <label className="grid gap-0.5">Infected parcel
            <select className={field} value={src} onChange={(e) => { setSrc(e.target.value); void run(e.target.value, false); }}>
              {sources.map((q) => <option key={q.parcel_id} value={q.parcel_id}>{q.parcel_id} · {q.issue}</option>)}
            </select>
          </label>
          <button type="button" disabled={busy} onClick={() => void run()} className="rounded-lg bg-primary px-3 py-1.5 font-semibold text-primary-foreground disabled:opacity-50">{busy ? "Working…" : "Re-run"}</button>
          <button type="button" disabled={busy} onClick={() => void run(src, false)} className="rounded-lg border border-border px-3 py-1.5">Reset assumptions</button>
        </div>
        {err && <p className="mt-1 text-destructive">{err}</p>}
      </div>

      {econ && (
        <div className="rounded-lg border border-border p-2.5" data-testid="regret-econ">
          <p className="mb-1 font-semibold">The cost of the missed moment (you enter the numbers)</p>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            <label className="grid gap-0.5">Yield t/ha<input className={field} inputMode="decimal" value={yieldT} onChange={(e) => setYieldT(e.target.value)} /></label>
            <label className="grid gap-0.5">Price Rs/quintal<input className={field} inputMode="decimal" value={price} onChange={(e) => setPrice(e.target.value)} placeholder="enter price" /></label>
            <label className="grid gap-0.5">Loss share %<input className={field} inputMode="decimal" value={loss} onChange={(e) => setLoss(e.target.value)} /></label>
            <label className="grid gap-0.5">Your cost of prevention Rs<input className={field} inputMode="decimal" value={cost} onChange={(e) => setCost(e.target.value)} placeholder="enter cost" /></label>
          </div>
          <dl className="mt-2 grid grid-cols-2 gap-x-3 gap-y-1 rounded-lg bg-muted/40 p-2.5">
            <dt className="text-muted-foreground">Parcel area</dt><dd className="text-right font-mono">{res.economics.area_ha} ha ({res.economics.area_acre} acres)</dd>
            <dt className="text-muted-foreground">Crop at stake</dt><dd className="text-right font-mono">{rs(econ.value)}</dd>
            <dt className="font-semibold">Possible loss</dt><dd className="text-right font-mono font-semibold">{rs(econ.lossRs)}</dd>
            <dt className="font-semibold">Regret (loss minus prevention cost)</dt><dd className="text-right font-mono font-semibold">{econ.regret == null ? "enter your cost" : rs(econ.regret)}</dd>
          </dl>
          <p className="mt-1 text-[10.5px] text-muted-foreground">{res.economics.note} Yield and price come from this parcel's own history and the {res.economics.price_basis}.</p>
        </div>
      )}

      <div>
        <p className="mb-1 font-semibold">
          Who is in the same position now? {res.source.crop} parcels, next 72 hours: <span className="text-[#ef4444]">{res.summary.act_now} act now</span> · <span className="text-[#f59e0b]">{res.summary.prepare} prepare</span> · {res.summary.monitor} monitor
        </p>
        <p className="mb-1 text-[10.5px] text-muted-foreground">
          {res.now.in_window ? `A suitable weather window is open now (about ${res.now.hours_left} h left).` : res.now.hours_to_open != null ? `Next suitable window opens in about ${res.now.hours_to_open} h.` : "No suitable window in the next 72 hours."} The weather is the same for every parcel (one forecast point), so they differ by crop stage.
        </p>
        <div ref={div} className="mb-2 h-64 w-full overflow-hidden rounded-lg border border-border" aria-label="Village map coloured by the action needed" />
        <ul className="grid gap-1">
          {res.twins.slice(0, 8).map((t) => {
            const left = t.hours_to_open != null ? t.hours_to_open * 3600 - elapsed : null;
            return (
              <li key={t.parcel_id} className="grid grid-cols-[52px_82px_minmax(0,1fr)_96px] items-center gap-2 rounded-md border border-border px-2 py-1.5">
                <b>{t.parcel_id}</b>
                <span className="rounded px-1.5 py-0.5 text-center font-mono text-[10px] font-bold text-black" style={{ background: ACT_COLOR[t.act], color: t.act === "MONITOR" ? "#fff" : "#000" }}>{t.act}</span>
                <span className="min-w-0 text-[10.5px] text-muted-foreground">{t.stage} · temp {t.checks.temperature ? "✓" : "✗"} · humidity {t.checks.humidity ? "✓" : "✗"} · stage {t.checks.stage ? "✓" : "✗"}{t.downgrade_reason.length ? ` · ${t.downgrade_reason.join("; ")}` : ""}</span>
                <span className="text-right font-mono text-[11px]">{t.act === "MONITOR" ? "" : res.now.in_window ? "window open" : left != null ? hm(left) : ""}</span>
              </li>
            );
          })}
        </ul>
      </div>

      <div className={`rounded-lg border px-2.5 py-1.5 ${res.verification.passed ? "border-success/50" : "border-destructive/50"}`} data-testid="regret-verifier">
        {res.verification.passed ? "✅" : "⚠"} Triple-condition verifier (rules, no model): {res.verification.checked} parcel(s) marked ACT NOW or PREPARE, each passing temperature, humidity and crop stage.
        <span className="block text-[10px] text-muted-foreground">{res.verification.method}</span>
      </div>

      <div>
        <p className="mb-1 font-semibold">Where each number comes from</p>
        <ul className="grid gap-1">
          {res.evidence.map((e) => (
            <li key={e.claim} className="flex items-start gap-2">
              <span className={`shrink-0 rounded border px-1.5 py-0.5 font-mono text-[9.5px] uppercase ${e.kind.startsWith("TNAU") ? "border-success/50 text-success" : "border-warning/50 text-warning"}`}>{e.kind}</span>
              <span>{e.claim}{e.url ? <> · <a className="text-primary hover:underline" href={e.url} target="_blank" rel="noreferrer">{e.source}</a></> : null}</span>
            </li>
          ))}
        </ul>
        <p className="mt-1 text-[10.5px] text-warning">TNAU pages say only that these diseases spread by wind and like moist weather. Every threshold, run length and latency here is an editable assumption, so a window is a plausible explanation, not proof.</p>
      </div>

      <div className="rounded-lg border border-border p-2.5">
        <button type="button" onClick={() => void makeBrief()} disabled={briefBusy} className="rounded-full border border-primary/50 bg-primary/10 px-3 py-1.5 font-medium text-primary disabled:opacity-50">
          {briefBusy ? "Writing the notice…" : "📣 Write the early-warning notice (Tamil + English)"}
        </button>
        {brief && (
          <div className="mt-2 grid gap-2">
            <p className="whitespace-pre-wrap rounded-md bg-muted/40 p-2" lang="ta">{brief.tamil}</p>
            <p className="whitespace-pre-wrap rounded-md bg-muted/40 p-2">{brief.english}</p>
            <p className="font-mono text-[10px] text-muted-foreground">{brief.model} · ${brief.cost_usd.toFixed(5)} · {brief.latency_ms} ms{brief.cached ? " · cached" : ""}{brief.note ? ` · ${brief.note}` : ""}</p>
          </div>
        )}
      </div>

      <ul className="list-disc space-y-0.5 pl-4 text-[10.5px] text-muted-foreground">
        {res.data_quality.map((d) => <li key={d}>{d}</li>)}
        <li>Analysis took {res.latency_ms} ms and cost $0 (no model call).</li>
      </ul>
    </div>
  );
}
