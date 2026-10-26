import { useEffect, useRef, useState } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { getApiSettings, type SpreadResult } from "@/lib/cropsy-api";
import { VILLAGE_PARCELS } from "@/data/villageParcels.generated";

const COLORS: Record<string, string> = { red: "#ef4444", amber: "#f59e0b", watch: "#facc15", low: "#4ade80", none: "#6b7280" };
const LABEL: Record<string, string> = { red: "HIGH", amber: "LIKELY", watch: "WATCH", low: "low", none: "not at risk" };
const DIRS: [string, number][] = [["N", 0], ["NE", 45], ["E", 90], ["SE", 135], ["S", 180], ["SW", 225], ["W", 270], ["NW", 315]];
const base = () => (getApiSettings().baseUrl || "").replace(/\/$/, "");

type Src = { parcel_id: string; issue: string; neighbours_in_reach: number };
type Alert = { tamil: string; english: string; model: string; cost_usd: number; latency_ms: number; note?: string; cached?: boolean };

/** Village spread-risk scan: a map of all parcels coloured by exposure risk, the wind, the plan, the evidence, a re-run with typed-in wind, and the village alert. */
export function SpreadPanel({ initial, sources }: { initial: SpreadResult; sources: Src[] }) {
  const [res, setRes] = useState<SpreadResult>(initial);
  const [src, setSrc] = useState(initial.source.parcel_id);
  const [dir, setDir] = useState<number | "">("");
  const [speed, setSpeed] = useState(14);
  const [useTyped, setUseTyped] = useState(false);
  const [fav, setFav] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [alert, setAlert] = useState<Alert | null>(null);
  const [alertBusy, setAlertBusy] = useState(false);
  const div = useRef<HTMLDivElement>(null);
  const map = useRef<L.Map | null>(null);
  const layer = useRef<L.LayerGroup | null>(null);

  const body = (parcel = src) => ({ source_parcel: parcel, favourable: fav, ...(useTyped && dir !== "" ? { wind_from_deg: dir, wind_speed_kmh: speed } : {}) });

  async function run(parcel = src, typed = useTyped) {
    setBusy(true);
    setErr("");
    setAlert(null);
    try {
      const b = { source_parcel: parcel, favourable: fav, ...(typed && dir !== "" ? { wind_from_deg: dir, wind_speed_kmh: speed } : {}) };
      const r = await fetch(`${base()}/api/spread`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(b) });
      const d = await r.json();
      if (!r.ok) throw new Error(d.detail || `error ${r.status}`);
      setRes(d);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "scan failed");
    } finally {
      setBusy(false);
    }
  }

  async function makeAlert() {
    setAlertBusy(true);
    setErr("");
    try {
      const r = await fetch(`${base()}/api/spread/alert`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body(res.source.parcel_id)) });
      const d = await r.json();
      if (!r.ok) throw new Error(d.detail || `error ${r.status}`);
      setAlert(d);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "alert failed");
    } finally {
      setAlertBusy(false);
    }
  }

  useEffect(() => {
    if (!div.current || map.current) return;
    const m = L.map(div.current, { zoomControl: true, attributionControl: true, scrollWheelZoom: false });
    L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}", { maxNativeZoom: 17, maxZoom: 18, attribution: "Esri World Imagery" }).addTo(m);
    map.current = m;
    layer.current = L.layerGroup().addTo(m);
    m.fitBounds(L.latLngBounds(VILLAGE_PARCELS.flatMap((p) => p.coords)).pad(0.05));
    setTimeout(() => m.invalidateSize(), 200);
    return () => {
      m.remove();
      map.current = null;
    };
  }, []);

  useEffect(() => {
    const g = layer.current;
    if (!g) return;
    g.clearLayers();
    const byId = new Map(res.parcels.map((p) => [p.parcel_id, p]));
    VILLAGE_PARCELS.forEach((p) => {
      const r = byId.get(p.id);
      const isSrc = p.id === res.source.parcel_id;
      const level = r?.level ?? "none";
      const color = isSrc ? "#a855f7" : COLORS[level];
      const poly = L.polygon(p.coords, { color, weight: isSrc ? 4 : level === "red" || level === "amber" ? 3 : 1, fillColor: color, fillOpacity: isSrc ? 0.55 : level === "none" ? 0.08 : 0.5 }).addTo(g);
      poly.bindTooltip(
        isSrc
          ? `${p.id}: INFECTED (${res.source.disease}, recorded)`
          : `${p.id} · ${r?.crop ?? p.crop} · ${r ? `${r.distance_m} m ${r.bearing_compass}` : ""}<br/>${level === "none" ? (r?.why ?? "not at risk") : `risk ${r?.risk} (${LABEL[level]})${r?.hours_to_threshold ? ` · about ${r.hours_to_threshold} h to threshold` : ""}`}`,
        { sticky: true },
      );
    });
    // zoom to the infected parcel and the parcels that can be reached from it, so the colours are readable
    const ids = new Set([res.source.parcel_id, ...res.parcels.filter((r) => r.crop === res.source.crop && r.distance_m <= res.disease.max_m).map((r) => r.parcel_id)]);
    const pts = VILLAGE_PARCELS.filter((p) => ids.has(p.id)).flatMap((p) => p.coords);
    if (pts.length && map.current) map.current.fitBounds(L.latLngBounds(pts).pad(0.3), { maxZoom: 16 });
  }, [res]);

  const susceptible = res.parcels.filter((p) => p.crop === res.source.crop && p.distance_m <= res.disease.max_m);
  const flagged = susceptible.filter((p) => p.risk >= res.threshold);
  const toward = (res.wind.from_deg + 180) % 360;
  const kindColor = (k: string) => (k.startsWith("TNAU") ? "text-success border-success/50" : "text-warning border-warning/50");

  return (
    <div className="mt-2 grid gap-3 text-xs" data-testid="spread-panel">
      <div className="relative">
        <div ref={div} className="h-80 w-full overflow-hidden rounded-lg border border-border" aria-label="Village map coloured by spread risk" />
        <div className="pointer-events-none absolute right-2 top-2 z-[500] rounded-lg bg-black/70 p-2 text-center text-[10px] text-white">
          <svg width="34" height="34" viewBox="0 0 34 34" style={{ transform: `rotate(${toward}deg)`, transition: "transform .4s" }} aria-label={`Wind blows toward ${res.wind.toward_compass}`}>
            <path d="M17 3 L26 25 L17 20 L8 25 Z" fill="#38bdf8" stroke="#fff" strokeWidth="1.2" />
          </svg>
          <div>wind from {res.wind.from_compass}</div>
          <div className="font-mono">{res.wind.mean_speed_kmh} km/h</div>
        </div>
        <div className="pointer-events-none absolute bottom-2 left-2 z-[500] flex flex-wrap gap-1 rounded-lg bg-black/70 p-1.5 text-[10px] text-white">
          <span style={{ color: "#a855f7" }}>■ infected</span><span style={{ color: COLORS.red }}>■ high</span><span style={{ color: COLORS.amber }}>■ likely</span>
          <span style={{ color: COLORS.watch }}>■ watch</span><span style={{ color: COLORS.low }}>■ low</span><span style={{ color: COLORS.none }}>■ not at risk</span>
        </div>
      </div>

      <div className="rounded-lg border border-border bg-muted/30 p-2.5">
        <div className="flex flex-wrap items-end gap-2">
          <label className="grid gap-0.5">Infected parcel
            <select className="rounded-md border border-border bg-background px-2 py-1" value={src} onChange={(e) => { setSrc(e.target.value); void run(e.target.value); }}>
              {sources.map((s) => <option key={s.parcel_id} value={s.parcel_id}>{s.parcel_id} · {s.issue} ({s.neighbours_in_reach} neighbours)</option>)}
            </select>
          </label>
          <label className="grid gap-0.5">Wind from
            <select className="rounded-md border border-border bg-background px-2 py-1" value={dir} onChange={(e) => { const v = e.target.value === "" ? "" : Number(e.target.value); setDir(v); setUseTyped(v !== ""); }}>
              <option value="">live forecast</option>
              {DIRS.map(([n, d]) => <option key={n} value={d}>{n}</option>)}
            </select>
          </label>
          <label className="grid gap-0.5">Speed {speed} km/h
            <input type="range" min={0} max={30} value={speed} onChange={(e) => setSpeed(Number(e.target.value))} />
          </label>
          <label className="flex items-center gap-1"><input type="checkbox" checked={fav} onChange={(e) => setFav(e.target.checked)} /> assume favourable weather</label>
          <button type="button" disabled={busy} onClick={() => void run()} className="rounded-lg bg-primary px-3 py-1.5 font-semibold text-primary-foreground disabled:opacity-50">{busy ? "Scanning…" : "Re-run scan"}</button>
        </div>
        <p className="mt-1 text-[10.5px] text-muted-foreground">Change the wind or the infected parcel and the map updates at once: the scan is arithmetic, not a stored answer. Typed-in wind replaces the forecast wind for all 72 hours.</p>
        {err && <p className="mt-1 text-destructive">{err}</p>}
      </div>

      <div>
        <p className="mb-1 font-semibold">
          {res.source.disease} on {res.source.parcel_id} ({res.source.crop}, {res.source.stage}): {susceptible.length} {res.source.crop.toLowerCase()} parcels in reach, {flagged.length} above the threshold
          <span className="font-normal text-muted-foreground"> · {res.latency_ms} ms · cost $0 (no model call)</span>
        </p>
        {susceptible.length === 0 ? (
          <p className="text-muted-foreground">No susceptible parcels within {res.disease.max_m} m of this parcel in this demo village.</p>
        ) : (
          <ul className="grid gap-1">
            {susceptible.slice(0, 7).map((p) => (
              <li key={p.parcel_id} className="grid grid-cols-[56px_minmax(0,1fr)_74px] items-center gap-2 rounded-md border border-border px-2 py-1.5" title={p.why}>
                <b>{p.parcel_id}</b>
                <span className="min-w-0">
                  <span className="block h-2 overflow-hidden rounded-full bg-muted"><span className="block h-full rounded-full" style={{ width: `${p.risk}%`, background: COLORS[p.level] }} /></span>
                  <span className="text-[10px] text-muted-foreground">{p.distance_m} m {p.bearing_compass} · {p.stage} · {p.downwind ? "downwind" : "not mainly downwind"}</span>
                </span>
                <span className="text-right font-mono">{p.risk} <span style={{ color: COLORS[p.level] }}>{LABEL[p.level]}</span>{p.hours_to_threshold ? <span className="block text-[10px] text-muted-foreground">~{p.hours_to_threshold} h</span> : null}</span>
              </li>
            ))}
          </ul>
        )}
        <p className="mt-1 text-[10.5px] text-muted-foreground">Risk 0 to 100 is an exposure index; "~h" is when it first reaches {res.threshold} within the next {res.horizon_hours} hours. It is not the time symptoms will show.</p>
      </div>

      <div className={`rounded-lg border px-2.5 py-1.5 ${res.verification.passed ? "border-success/50" : "border-destructive/50"}`} data-testid="geometry-verifier">
        {res.verification.passed ? "✅" : "⚠"} Geometry verifier (plain arithmetic, no model): {res.verification.checked} flagged parcel(s) checked, {res.verification.failed.length} failed.
        <span className="block text-[10px] text-muted-foreground">{res.verification.method}</span>
      </div>

      <div>
        <p className="mb-1 font-semibold">Where each number comes from</p>
        <ul className="grid gap-1">
          {res.disease.evidence.map((e) => (
            <li key={e.claim} className="flex items-start gap-2">
              <span className={`shrink-0 rounded border px-1.5 py-0.5 font-mono text-[9.5px] uppercase ${kindColor(e.kind)}`}>{e.kind}</span>
              <span>{e.claim}{e.url ? <> · <a className="text-primary hover:underline" href={e.url} target="_blank" rel="noreferrer">{e.source}</a></> : null}</span>
            </li>
          ))}
        </ul>
        <p className="mt-1 text-[10.5px] text-warning">TNAU pages give the qualitative facts (wind-borne spores, moist weather). They do not give a spore distance or exact weather thresholds, so those are labelled assumptions.</p>
      </div>

      <div className="rounded-lg border border-border p-2.5">
        <button type="button" onClick={() => void makeAlert()} disabled={alertBusy} className="rounded-full border border-primary/50 bg-primary/10 px-3 py-1.5 font-medium text-primary disabled:opacity-50">
          {alertBusy ? "Writing the notice…" : "📣 Write the village alert (Tamil + English)"}
        </button>
        {alert && (
          <div className="mt-2 grid gap-2">
            <p className="whitespace-pre-wrap rounded-md bg-muted/40 p-2" lang="ta">{alert.tamil}</p>
            <p className="whitespace-pre-wrap rounded-md bg-muted/40 p-2">{alert.english}</p>
            <p className="font-mono text-[10px] text-muted-foreground">{alert.model} · ${alert.cost_usd.toFixed(5)} · {alert.latency_ms} ms{alert.cached ? " · cached" : ""}{alert.note ? ` · ${alert.note}` : ""}</p>
          </div>
        )}
      </div>

      <ul className="list-disc space-y-0.5 pl-4 text-[10.5px] text-muted-foreground">
        {res.data_quality.map((n) => <li key={n}>{n}</li>)}
      </ul>
    </div>
  );
}
