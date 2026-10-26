import React, { useEffect, useMemo, useState } from "react";
import { fetchIndexResults, type IndexResults, type IndexSeries } from "@/lib/cropsy-api";
import { lut } from "@/lib/colormaps";
import { Badge, Card, Empty } from "./ui";

const ORDER = ["ndvi", "evi", "savi", "ndre", "ndmi", "ndwi", "rvi", "rsm"] as const;
const COLORS = { a: "#18b894", b: "var(--warning)", village: "color-mix(in oklab, var(--muted-foreground) 70%, transparent)", ghost: "#b79cf8" };
const iso = (d: Date) => d.toISOString().slice(0, 10);
const addDays = (s: string, n: number) => iso(new Date(new Date(s).getTime() + n * 86400000));
const fmt = (v: number | null | undefined, d = 2) => (v == null ? "n/a" : v.toFixed(d));

/** A tiny trend line for a tile. */
const Spark: React.FC<{ s: IndexSeries }> = ({ s }) => {
  const p = s.points;
  if (p.length < 2) return <div className="h-8 text-[10px] text-muted-foreground/70">too few clear views</div>;
  const lo = Math.min(...p.map((x) => x.value)), hi = Math.max(...p.map((x) => x.value));
  const pts = p.map((x, i) => `${(i / (p.length - 1)) * 100},${30 - ((x.value - lo) / (hi - lo || 1)) * 26 - 2}`).join(" ");
  return <svg viewBox="0 0 100 30" preserveAspectRatio="none" className="w-full h-8"><polyline fill="none" stroke={COLORS.a} strokeWidth="1.6" points={pts} /></svg>;
};

/** Main chart: index A on the left axis, optional index B on the right axis, village median dashed for A. */
const Chart: React.FC<{ a: IndexSeries; b: IndexSeries | null; ghost?: IndexSeries | null; start: string; end: string; showVillage: boolean }> = ({ a, b, ghost, start, end, showVillage }) => {
  const W = 760, H = 270, L = 46, R = b ? 46 : 14, T = 12, B = 30;
  const t0 = new Date(start).getTime(), t1 = new Date(end).getTime();
  const x = (d: string) => L + ((new Date(d).getTime() - t0) / (t1 - t0 || 1)) * (W - L - R);
  const range = (s: IndexSeries, withVillage: boolean) => {
    const v = [...s.points, ...(s === a && ghost ? ghost.points : [])].flatMap((p) => [p.value, ...(withVillage && p.village_median != null ? [p.village_median] : [])]);
    if (!v.length) return [0, 1] as const;
    const lo = Math.min(...v), hi = Math.max(...v), pad = (hi - lo || 0.1) * 0.12;
    return [lo - pad, hi + pad] as const;
  };
  const ra = range(a, showVillage), rb = b ? range(b, false) : ([0, 1] as const);
  const ya = (v: number) => T + (1 - (v - ra[0]) / (ra[1] - ra[0])) * (H - T - B);
  const yb = (v: number) => T + (1 - (v - rb[0]) / (rb[1] - rb[0])) * (H - T - B);
  const line = (pts: { date: string; v: number }[], y: (v: number) => number) => pts.map((p) => `${x(p.date)},${y(p.v)}`).join(" ");
  const months: string[] = [];
  for (let d = new Date(start.slice(0, 7) + "-01"); d.getTime() <= t1; d = new Date(d.getFullYear(), d.getMonth() + 1, 1)) if (d.getTime() >= t0) months.push(iso(d));
  const ticks = Array.from({ length: 5 }, (_, i) => ra[0] + ((ra[1] - ra[0]) * i) / 4);
  const tickB = Array.from({ length: 5 }, (_, i) => rb[0] + ((rb[1] - rb[0]) * i) / 4);
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full">
      {ticks.map((t, i) => (
        <g key={i}>
          <line x1={L} x2={W - R} y1={ya(t)} y2={ya(t)} stroke="var(--border)" strokeWidth="0.6" />
          <text x={L - 6} y={ya(t) + 3} textAnchor="end" fontSize="9" fill={COLORS.a} fontFamily="monospace">{t.toFixed(2)}</text>
        </g>
      ))}
      {b && tickB.map((t, i) => <text key={i} x={W - R + 6} y={yb(t) + 3} fontSize="9" fill={COLORS.b} fontFamily="monospace">{t.toFixed(2)}</text>)}
      {months.map((m) => (
        <g key={m}>
          <line x1={x(m)} x2={x(m)} y1={T} y2={H - B} stroke="var(--border)" strokeWidth="0.4" strokeDasharray="2 3" />
          <text x={x(m)} y={H - 12} fontSize="9" fill="color-mix(in oklab, var(--muted-foreground) 70%, transparent)" textAnchor="middle" fontFamily="monospace">{m.slice(5, 7)}/{m.slice(2, 4)}</text>
        </g>
      ))}
      {ghost && ghost.points.length > 0 && (
        <polyline fill="none" stroke={COLORS.ghost} strokeWidth="1.6" strokeDasharray="5 3" points={line(ghost.points.map((p) => ({ date: p.date, v: p.value })), ya)} />
      )}
      {showVillage && (
        <polyline fill="none" stroke={COLORS.village} strokeWidth="1.2" strokeDasharray="4 3"
          points={line(a.points.filter((p) => p.village_median != null).map((p) => ({ date: p.date, v: p.village_median as number })), ya)} />
      )}
      <polyline fill="none" stroke={COLORS.a} strokeWidth="2" points={line(a.points.map((p) => ({ date: p.date, v: p.value })), ya)} />
      {a.points.map((p) => <circle key={p.date} cx={x(p.date)} cy={ya(p.value)} r="2.6" fill={COLORS.a}><title>{`${a.name} ${p.date}: ${p.value}`}</title></circle>)}
      {b && <polyline fill="none" stroke={COLORS.b} strokeWidth="2" points={line(b.points.map((p) => ({ date: p.date, v: p.value })), yb)} />}
      {b && b.points.map((p) => <circle key={p.date} cx={x(p.date)} cy={yb(p.value)} r="2.6" fill={COLORS.b}><title>{`${b.name} ${p.date}: ${p.value}`}</title></circle>)}
    </svg>
  );
};

/** Compass: 8 wedges coloured by NDVI relative to the field's own range; the weakest side is outlined. */
const Compass: React.FC<{ d: NonNullable<IndexResults["field_directions"]> }> = ({ d }) => {
  const names = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"];
  const vals = Object.values(d.sectors);
  const lo = Math.min(...vals), hi = Math.max(...vals);
  const l = lut("RdYlGn");
  const wedge = (i: number) => {
    const a0 = ((i * 45 - 22.5 - 90) * Math.PI) / 180, a1 = ((i * 45 + 22.5 - 90) * Math.PI) / 180, r = 56;
    return `M60 60 L${60 + r * Math.cos(a0)} ${60 + r * Math.sin(a0)} A${r} ${r} 0 0 1 ${60 + r * Math.cos(a1)} ${60 + r * Math.sin(a1)} Z`;
  };
  return (
    <svg viewBox="0 0 120 120" className="w-36 h-36">
      {names.map((n, i) => {
        const v = d.sectors[n];
        const t = v == null ? null : (v - lo) / (hi - lo || 1);
        const c = t == null ? "var(--border)" : `rgb(${l[Math.round(40 + t * 190)].join(",")})`;
        const mid = ((i * 45 - 90) * Math.PI) / 180;
        return (
          <g key={n}>
            <path d={wedge(i)} fill={c} stroke={n === d.weakest ? "#fff" : "var(--background)"} strokeWidth={n === d.weakest ? 2 : 1}><title>{`${n}: NDVI ${v ?? "n/a"}`}</title></path>
            <text x={60 + 44 * Math.cos(mid)} y={63 + 44 * Math.sin(mid)} fontSize="8" textAnchor="middle" fill="var(--background)" fontWeight="700">{n}</text>
          </g>
        );
      })}
    </svg>
  );
};

export const IndexResultsPanel: React.FC<{ parcelId: string }> = ({ parcelId }) => {
  const today = iso(new Date());
  const [start, setStart] = useState(addDays(today, -365));
  const [end, setEnd] = useState(today);
  const [applied, setApplied] = useState({ start: addDays(today, -365), end: today });
  const [data, setData] = useState<IndexResults | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [a, setA] = useState<string>("ndvi");
  const [b, setB] = useState<string>("");
  const [village, setVillage] = useState(true);
  const [lastYear, setLastYear] = useState(false);
  const [prevData, setPrevData] = useState<IndexResults | null>(null);

  useEffect(() => {
    let live = true;
    setData(null);
    setError(null);
    fetchIndexResults(parcelId, applied.start, applied.end).then((r) => live && setData(r)).catch((e) => live && setError(e.message));
    return () => { live = false; };
  }, [parcelId, applied]);

  // the same calendar dates one year earlier, drawn on top of this season (dates shifted forward a year so the seasons line up)
  useEffect(() => {
    let live = true;
    if (!lastYear) { setPrevData(null); return; }
    fetchIndexResults(parcelId, addDays(applied.start, -365), addDays(applied.end, -365)).then((r) => live && setPrevData(r)).catch(() => live && setPrevData(null));
    return () => { live = false; };
  }, [lastYear, parcelId, applied]);
  const ghost: IndexSeries | null = useMemo(() => {
    const g = prevData?.indices[a];
    return g ? { ...g, points: g.points.map((p) => ({ ...p, date: addDays(p.date, 365) })) } : null;
  }, [prevData, a]);

  const preset = (days: number) => { const e = today, s = addDays(today, -days); setStart(s); setEnd(e); setApplied({ start: s, end: e }); };
  const sa = data?.indices[a] || null;
  const sb = b ? data?.indices[b] || null : null;

  const csv = useMemo(() => {
    if (!data) return "";
    const dates = Array.from(new Set(ORDER.flatMap((k) => data.indices[k]?.points.map((p) => p.date) || []))).sort();
    const head = ["date", ...ORDER.map((k) => data.indices[k]?.name || k)];
    const rows = dates.map((d) => [d, ...ORDER.map((k) => data.indices[k]?.points.find((p) => p.date === d)?.value ?? "")]);
    return [head, ...rows].map((r) => r.join(",")).join("\n");
  }, [data]);
  const download = () => {
    const url = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
    const el = document.createElement("a");
    el.href = url;
    el.download = `${parcelId}_index_results_${applied.start}_${applied.end}.csv`;
    el.click();
    URL.revokeObjectURL(url);
  };

  const cal = data?.calendar;
  const inWin = (d: string) => d >= applied.start && d <= applied.end;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end gap-3">
        <h2 className="font-serif text-base font-semibold text-foreground mr-2">Index results · {parcelId}</h2>
        <label className="text-[11px] text-muted-foreground/70 flex flex-col">From
          <input type="date" value={start} max={end} onChange={(e) => setStart(e.target.value)} className="bg-background border border-border rounded px-2 py-1 text-xs text-foreground" />
        </label>
        <label className="text-[11px] text-muted-foreground/70 flex flex-col">To
          <input type="date" value={end} min={start} max={today} onChange={(e) => setEnd(e.target.value)} className="bg-background border border-border rounded px-2 py-1 text-xs text-foreground" />
        </label>
        <button onClick={() => setApplied({ start, end })} className="rounded bg-success px-3 py-1.5 text-xs font-semibold text-background hover:opacity-90">Apply</button>
        {[["30 d", 30], ["90 d", 90], ["6 mo", 183], ["1 yr", 365]].map(([l, n]) => (
          <button key={l as string} onClick={() => preset(n as number)} className="rounded-full border border-border px-2.5 py-1 text-[11px] text-muted-foreground hover:text-foreground">{l}</button>
        ))}
        <button onClick={download} disabled={!data} className="ml-auto rounded border border-border px-3 py-1.5 text-xs text-foreground hover:border-success/60 disabled:opacity-40">Export CSV</button>
      </div>

      {error && <Empty>{error}. Start the backend (port 8000).</Empty>}
      {!error && !data && <Empty>Loading index results…</Empty>}

      {data && (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {ORDER.map((k) => {
              const s = data.indices[k];
              if (!s) return null;
              const ch = s.change_vs_previous;
              return (
                <button key={k} onClick={() => setA(k)} className={`text-left rounded-xl border p-3 flex flex-col gap-1 transition-colors ${a === k ? "border-success bg-success/10" : "border-border bg-card hover:border-success/40"}`}>
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-foreground">{s.name}</span>
                    <span className="font-mono text-[9px] text-muted-foreground/70">{s.sensor}</span>
                  </div>
                  <div className="flex items-baseline gap-2">
                    <span className="font-mono text-xl text-foreground">{fmt(s.latest?.value)}</span>
                    <span className={`font-mono text-[11px] ${ch == null ? "text-muted-foreground/70" : ch >= 0 ? "text-success" : "text-warning"}`}>
                      {ch == null ? "no prior window" : `${ch >= 0 ? "▲" : "▼"} ${Math.abs(ch).toFixed(2)}`}
                    </span>
                  </div>
                  <Spark s={s} />
                  <span className="text-[10px] text-muted-foreground/70">{s.n_points} clear views · latest {s.latest?.date ?? "none"}</span>
                </button>
              );
            })}
          </div>

          <Card title={`${sa?.name || a} over time`} right={
            <div className="flex items-center gap-2 text-[11px] text-muted-foreground">
              <label className="flex items-center gap-1"><input type="checkbox" checked={village} onChange={(e) => setVillage(e.target.checked)} /> village median</label>
              <label className="flex items-center gap-1"><input type="checkbox" checked={lastYear} onChange={(e) => setLastYear(e.target.checked)} /> same dates last year</label>
              <span>compare with</span>
              <select value={b} onChange={(e) => setB(e.target.value)} className="bg-background border border-border rounded px-1.5 py-0.5 text-xs text-foreground">
                <option value="">none</option>
                {ORDER.filter((k) => k !== a).map((k) => <option key={k} value={k}>{data.indices[k]?.name || k}</option>)}
              </select>
            </div>
          }>
            {sa && sa.points.length > 0 ? (
              <>
                <Chart a={sa} b={sb} ghost={ghost} start={applied.start} end={applied.end} showVillage={village} />
                <div className="flex flex-wrap gap-3 text-[11px] font-mono">
                  <span style={{ color: COLORS.a }}>● {sa.name} (left axis)</span>
                  {sb && <span style={{ color: COLORS.b }}>● {sb.name} (right axis)</span>}
                  {village && <span style={{ color: COLORS.village }}>┅ village median of {sa.name}</span>}
                  {lastYear && <span style={{ color: COLORS.ghost }}>╌ {sa.name}, same dates last year{ghost && ghost.points.length === 0 ? " (no clear views)" : ""}</span>}
                </div>
                <p className="text-[11px] text-muted-foreground">{sa.meaning} <span className="text-muted-foreground/70">Formula: {sa.formula}.</span></p>
                <p className="text-[11px] text-muted-foreground">
                  Window mean {fmt(sa.window_mean)} vs {fmt(sa.previous_mean)} in the previous {data.previous_window[0]} to {data.previous_window[1]}
                  {sa.change_vs_previous != null ? ` (${sa.change_vs_previous >= 0 ? "+" : ""}${sa.change_vs_previous.toFixed(3)}).` : " (no earlier data to compare)."}
                </p>
              </>
            ) : (
              <Empty>No clear {sa?.sensor || ""} observation of this parcel in the chosen window. Widen the dates{sa?.sensor === "Sentinel-2" ? ", or look at the radar indices, which see through cloud" : ""}.</Empty>
            )}
          </Card>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <Card title="Satellite pass calendar" right={<Badge tone="ok">real passes</Badge>}>
              {cal && (
                <>
                  <p className="text-[11px] text-muted-foreground/70">Optical (Sentinel-2): each dot is a pass. Green = most parcels clear, amber = some, grey = clouded out.</p>
                  <div className="flex flex-wrap gap-1">
                    {cal.sentinel2.filter((p) => inWin(p.date)).map((p) => (
                      <span key={p.date} title={`${p.date} · scene cloud ${p.scene_cloud_pct}% · ${p.parcels_clear} of 120 parcels clear`}
                        className={`inline-block w-3 h-3 rounded-full ${p.parcels_clear >= 60 ? "bg-success" : p.parcels_clear > 0 ? "bg-warning" : "bg-muted-foreground/40"}`} />
                    ))}
                  </div>
                  <p className="text-[11px] text-muted-foreground/70 pt-1">Radar (Sentinel-1): works through cloud.</p>
                  <div className="flex flex-wrap gap-1">
                    {cal.sentinel1.filter((p) => inWin(p.date)).map((p) => (
                      <span key={p.date + p.orbit} title={`${p.date} · ${p.orbit} · ${p.parcels_observed} parcels`} className="inline-block w-3 h-3 rounded-sm bg-[#5b8def]" />
                    ))}
                  </div>
                  <p className="text-[11px] text-muted-foreground">{cal.sentinel2.filter((p) => inWin(p.date) && p.parcels_clear > 0).length} usable optical passes and {cal.sentinel1.filter((p) => inWin(p.date)).length} radar passes in this window.</p>
                </>
              )}
            </Card>

            <Card title="Field directions: where to inspect first">
              {data.field_directions ? (
                <div className="flex items-center gap-4">
                  <Compass d={data.field_directions} />
                  <div className="text-xs text-muted-foreground flex flex-col gap-1">
                    <p className="text-foreground">{data.field_directions.note}</p>
                    <p>Weakest: <b>{data.field_directions.weakest}</b> · strongest: <b>{data.field_directions.strongest}</b> · spread {data.field_directions.spread}</p>
                    <p className="text-[10.5px] text-muted-foreground/70">{data.field_directions.basis} Pass of {data.field_directions.date}.</p>
                  </div>
                </div>
              ) : (
                <Empty>No clear recent pass with enough pixels in each direction for this parcel.</Empty>
              )}
            </Card>
          </div>
          <p className="text-[10.5px] text-muted-foreground/70">{data.data_source}. A falling index is a signal to inspect the field, not a diagnosis.</p>
        </>
      )}
    </div>
  );
};

export default IndexResultsPanel;
