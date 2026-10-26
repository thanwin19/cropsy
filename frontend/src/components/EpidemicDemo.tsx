import { useCallback, useEffect, useRef, useState } from "react";
import L from "leaflet";
import { Bug, Pause, Play, RotateCcw, X } from "lucide-react";
import { getApiSettings, type SpreadResult } from "@/lib/cropsy-api";
import { VILLAGE_PARCELS } from "@/data/villageParcels.generated";

const base = () => (getApiSettings().baseUrl || "").replace(/\/$/, "");
const COLORS: Record<string, string> = { red: "#ef4444", amber: "#f59e0b", watch: "#facc15", low: "#4ade80", none: "#6b7280" };
const DIRS: [string, number][] = [["live forecast", -1], ["N", 0], ["NE", 45], ["E", 90], ["SE", 135], ["S", 180], ["SW", 225], ["W", 270], ["NW", 315]];

type Src = { parcel_id: string; crop: string; issue: string; severity: string; code: string; neighbours_in_reach: number };
type Prev = { disease: string; crop: string; steps: string[]; tnau_passages: string[]; note: string; ask: string };
type Res = SpreadResult;

const levelOf = (r: number) => (r >= 70 ? "red" : r >= 50 ? "amber" : r >= 20 ? "watch" : r > 0 ? "low" : "none");
const at = (tl: number[] | undefined, h: number) => {
  if (!tl || !tl.length) return 0;
  const f = Math.min(tl.length - 1, h / 3), a = Math.floor(f), b = Math.min(tl.length - 1, a + 1);
  return tl[a] + (tl[b] - tl[a]) * (f - a);
};
/** Risk at an hour. If Cropsy's warning was acted on at hour `act`, a protected parcel (one that was going to cross the threshold) holds the risk it had then: a scenario assumption, not a measured spray efficacy. */
const effAt = (p: { timeline?: number[]; hours_to_threshold?: number | null } | undefined, h: number, act: number | null) =>
  act !== null && p?.hours_to_threshold && h > act ? at(p.timeline, act) : at(p?.timeline, h);
const dest = (lat: number, lon: number, bearing: number, m: number): [number, number] => {
  const R = 6371000, br = (bearing * Math.PI) / 180, p1 = (lat * Math.PI) / 180, l1 = (lon * Math.PI) / 180, d = m / R;
  const p2 = Math.asin(Math.sin(p1) * Math.cos(d) + Math.cos(p1) * Math.sin(d) * Math.cos(br));
  const l2 = l1 + Math.atan2(Math.sin(br) * Math.sin(d) * Math.cos(p1), Math.cos(d) - Math.sin(p1) * Math.sin(p2));
  return [(p2 * 180) / Math.PI, (l2 * 180) / Math.PI];
};

const NAMES = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"];
const compassName = (deg: number) => NAMES[Math.round((((deg % 360) + 360) % 360) / 22.5) % 16];
const centroid = (c: [number, number][]) => [c.reduce((a, p) => a + p[0], 0) / c.length, c.reduce((a, p) => a + p[1], 0) / c.length] as [number, number];
const CENTROIDS = new Map(VILLAGE_PARCELS.map((v) => [v.id, centroid(v.coords)]));

/** Draggable compass: drag the arrow to point where the wind blows; the whole scan is recomputed for that wind. */
function Compass({ from, speed, onDrag }: { from: number; speed: number; onDrag?: (fromDeg: number) => void }) {
  const toward = (from + 180) % 360;
  const move = (e: React.PointerEvent<SVGSVGElement>) => {
    if (!onDrag || e.buttons !== 1) return;
    const r = e.currentTarget.getBoundingClientRect();
    const ang = (Math.atan2(e.clientX - (r.left + r.width / 2), -(e.clientY - (r.top + r.height / 2))) * 180) / Math.PI;
    onDrag((Math.round(((((ang + 180) % 360) + 360) % 360) / 5) * 5) % 360);
  };
  return (
    <span className="inline-flex items-center gap-2" title="Drag the arrow to change the wind direction">
      <svg width="52" height="52" viewBox="-26 -26 52 52" className={onDrag ? "pointer-events-auto cursor-grab touch-none" : ""} onPointerDown={(e) => { e.currentTarget.setPointerCapture(e.pointerId); move(e); }} onPointerMove={move} aria-label="Wind compass">
        <circle r="23" fill="rgba(0,0,0,.35)" stroke="currentColor" strokeOpacity=".5" />
        <text y="-14" textAnchor="middle" fontSize="7" fill="currentColor">N</text>
        <g transform={`rotate(${toward})`}><path d="M0 -18 L7 8 L0 3 L-7 8 Z" fill="#38bdf8" stroke="#0c4a6e" /></g>
      </svg>
      <span className="leading-tight"><b>Wind from {compassName(from)}</b><br /><span className="text-muted-foreground">{speed} km/h{onDrag ? " · drag the arrow" : ""}</span></span>
    </span>
  );
}

/** A small map icon. Open it for what to do about a wind-borne disease, press Start to watch the next 72 hours of spread play out on the map. */
export function EpidemicDemo({ getMap, selectedId }: { getMap: () => L.Map | null; selectedId?: string }) {
  const [open, setOpen] = useState(false);
  const [srcs, setSrcs] = useState<Src[]>([]);
  const [src, setSrc] = useState("");
  const [res, setRes] = useState<Res | null>(null);
  const [prev, setPrev] = useState<Prev | null>(null);
  const [hour, setHour] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [dir, setDir] = useState(-1);
  const [speed, setSpeed] = useState(14);
  const [fav, setFav] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [mini, setMini] = useState(false);
  const [rate, setRate] = useState(1);
  const [econ, setEcon] = useState(false);
  const [bars, setBars] = useState(true);
  const [focus, setFocus] = useState(true);
  const [legend, setLegend] = useState(true);
  const [lossPct, setLossPct] = useState(30);
  const [kgHa, setKgHa] = useState("");
  const [spray, setSpray] = useState("");
  const [actHour, setActHour] = useState(6);
  const [acted, setActed] = useState(false);
  const [perHa, setPerHa] = useState("");
  const [voice, setVoice] = useState(false);
  const [replay, setReplay] = useState<{ data: any; ago: number } | null>(null);
  const [replayPlaying, setReplayPlaying] = useState(false);
  const group = useRef<L.LayerGroup | null>(null);
  const st = useRef<{ res: Res | null; hour: number; on: boolean; rate: number; act: number | null }>({ res: null, hour: 0, on: false, rate: 1, act: null });
  const spoken = useRef(0);
  const tmr = useRef<ReturnType<typeof setTimeout> | null>(null);

  function changeDir(d: number) {
    setDir(d); setPlaying(false); setHour(0); setReplay(null);
    if (tmr.current) clearTimeout(tmr.current);
    tmr.current = setTimeout(() => void load(src, d, speed, fav), 200);
  }

  async function startReplay() {
    setPlaying(false); setErr("");
    const ask = async (pid: string) => {
      const r = await fetch(`${base()}/api/regret`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ source_parcel: pid }) });
      const j = await r.json();
      return r.ok && j.available && j.reconstruction?.best ? j : null;
    };
    try {
      let pid = src, j = await ask(src);
      // this parcel's recorded symptom timing may not match any past weather window; try the other infected parcels so the replay still has something real to show
      for (const o of srcs) { if (j) break; pid = o.parcel_id; j = await ask(pid); }
      if (!j) throw new Error("No past weather window matched any infected parcel's recorded symptom timing, so there is nothing to replay.");
      if (pid !== src) { setSrc(pid); void load(pid); setErr(`No window matched ${src}'s symptom timing, so the replay uses ${pid}.`); }
      setMini(true);
      const map = getMap();
      const v = VILLAGE_PARCELS.find((x) => x.id === pid);
      if (map && v) map.fitBounds(L.latLngBounds(v.coords).pad(2.5), { maxZoom: 16, paddingBottomRight: [30, 200] });
      setReplay({ data: j, ago: Math.min(j.history.series.now_i, Math.max(336, j.reconstruction.best.hours_ago_at_start + 36)) });
      setReplayPlaying(true);
    } catch (e) { setErr(e instanceof Error ? e.message : "replay failed"); }
  }

  // wind speed works for the live forecast too: it pins the current wind direction and changes the speed
  function changeSpeed(v: number) {
    setSpeed(v);
    let d = dir;
    if (d < 0 && res) { d = Math.round(res.wind.from_deg); setDir(d); }
    if (tmr.current) clearTimeout(tmr.current);
    tmr.current = setTimeout(() => void load(src, d, v, fav), 250);
  }

  const clear = useCallback(() => {
    group.current?.remove();
    group.current = null;
  }, []);

  async function load(parcel: string, d = dir, sp = speed, f = fav): Promise<Res | null> {
    setBusy(true);
    setErr("");
    try {
      const body = { source_parcel: parcel, favourable: f, ...(d >= 0 ? { wind_from_deg: d, wind_speed_kmh: sp } : {}) };
      const r = await fetch(`${base()}/api/spread`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
      const j = await r.json();
      if (!r.ok) throw new Error(j.detail || `error ${r.status}`);
      setRes(j);
      fetch(`${base()}/api/spread/prevention?disease_code=${j.source.disease_code}`).then((x) => x.json()).then(setPrev).catch(() => setPrev(null));
      return j;
    } catch (e) {
      setErr(e instanceof Error ? e.message : "scan failed");
      return null;
    } finally {
      setBusy(false);
    }
  }

  // first open: list the infected parcels and scan the one with the most neighbours (so the demo is visible at once)
  useEffect(() => {
    if (!open || srcs.length) return;
    fetch(`${base()}/api/spread/sources`).then((r) => r.json()).then((d) => {
      const items: Src[] = d.items ?? [];
      setSrcs(items);
      const first = items.find((i) => i.parcel_id === selectedId) ?? items[0];   // start from the parcel the user has selected if it has a recorded wind-borne disease
      if (first) {
        setSrc(first.parcel_id);
        void load(first.parcel_id);
      }
    }).catch(() => setErr("Could not load infected parcels"));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  // focus mode: while the compact demo bar is up, hide the other map panels so the spread is what you see
  useEffect(() => {
    if (!(open && mini && focus)) return;
    document.body.classList.add("epi-cinema");
    return () => document.body.classList.remove("epi-cinema");
  }, [open, mini, focus]);

  // regret replay: time runs backwards from 14 days ago to now
  useEffect(() => {
    if (!replayPlaying) return;
    const id = setInterval(() => setReplay((r) => (r && r.ago > 0 ? { ...r, ago: Math.max(0, r.ago - 6) } : (setReplayPlaying(false), r))), 110 / rate);
    return () => clearInterval(id);
  }, [replayPlaying, rate]);

  // play
  useEffect(() => {
    if (!playing) return;
    const id = setInterval(() => setHour((h) => (h >= 72 ? (setPlaying(false), 72) : h + 1)), 230 / rate);
    return () => clearInterval(id);
  }, [playing, rate]);

  const windFrom = dir >= 0 ? dir : res?.wind.from_deg ?? 0;
  const mult = Number(perHa) > 0 ? Number(perHa) : 0;
  const areaOf = (id: string) => VILLAGE_PARCELS.find((v) => v.id === id)?.areaHa ?? 0;
  const actAt = acted ? actHour : null;
  st.current = { res, hour, on: !!res && !replay && (hour > 0 || playing), rate, act: actAt };

  // spore ribbons: animated particles on a canvas over the map, from the infected parcel to the parcels the wind is carrying spores to
  useEffect(() => {
    const map = getMap();
    if (!open || !map) return;
    const c = document.createElement("canvas");
    c.style.cssText = "position:absolute;left:0;top:0;pointer-events:none;z-index:450";
    map.getContainer().appendChild(c);
    const ctx = c.getContext("2d");
    let raf = 0;
    const loop = (now: number) => {
      const el = map.getContainer();
      if (c.width !== el.clientWidth || c.height !== el.clientHeight) { c.width = el.clientWidth; c.height = el.clientHeight; }
      ctx?.clearRect(0, 0, c.width, c.height);
      const { res: r, hour: hh, on, rate: rt, act } = st.current;
      if (ctx && r && on) {
        const sc = CENTROIDS.get(r.source.parcel_id);
        if (sc) {
          const a = map.latLngToContainerPoint(sc);
          r.parcels.forEach((p, idx) => {
            if (p.crop !== r.source.crop || p.distance_m > r.disease.max_m) return;
            const risk = effAt(p, hh, act);
            const tc = CENTROIDS.get(p.parcel_id);
            if (!tc || risk < 3) return;
            const b = map.latLngToContainerPoint(tc);
            const mx = (a.x + b.x) / 2, my = (a.y + b.y) / 2, dx = b.x - a.x, dy = b.y - a.y;
            const cx = mx - dy * 0.22, cy = my + dx * 0.22;
            const hot = risk >= r.threshold, col = hot ? "239,68,68" : "251,146,60";
            ctx.strokeStyle = `rgba(${col},${hot ? 0.55 : 0.32})`;
            ctx.lineWidth = 1 + risk / 22;
            ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.quadraticCurveTo(cx, cy, b.x, b.y); ctx.stroke();
            const n = Math.min(8, 2 + Math.ceil(risk / 14));
            for (let k = 0; k < n; k++) {
              const t = ((now * rt) / 2200 + k / n + idx * 0.137) % 1;
              const x = (1 - t) * (1 - t) * a.x + 2 * (1 - t) * t * cx + t * t * b.x, y = (1 - t) * (1 - t) * a.y + 2 * (1 - t) * t * cy + t * t * b.y;
              ctx.fillStyle = `rgba(${col},${0.9 - t * 0.4})`;
              ctx.beginPath(); ctx.arc(x, y, hot ? 3.4 : 2.6, 0, 7); ctx.fill();
            }
          });
        }
      }
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => { cancelAnimationFrame(raf); c.remove(); };
  }, [open, getMap]);

  // draw the parcels, countdown rings and wind arrows for the current hour (or the replayed past)
  useEffect(() => {
    const map = getMap();
    if (!open || !map || !res) return;
    clear();
    const g = L.layerGroup().addTo(map);
    group.current = g;
    const s = res.source;
    const sv = VILLAGE_PARCELS.find((v) => v.id === s.parcel_id);
    if (replay) {
      const rc = replay.data.reconstruction, best = rc.best;
      const startAgo = best.hours_ago_at_start, endAgo = startAgo - best.hours, symAgo = (rc.symptom_noted_days_ago || 0) * 24;
      const phase = replay.ago > startAgo ? "healthy" : replay.ago > endAgo ? "window" : replay.ago > symAgo ? "incubating" : "symptoms";
      const col = { healthy: "#22c55e", window: "#facc15", incubating: "#f59e0b", symptoms: "#ef4444" }[phase];
      const label = phase === "healthy" ? "healthy" : phase === "window" ? "weather window open" : phase === "incubating" ? "infected, not yet visible" : "symptoms recorded";
      if (sv) L.polygon(sv.coords, { color: col, weight: 5, fillColor: col, fillOpacity: 0.55, className: phase === "window" ? "epi-pulse" : "" }).bindTooltip(`${s.parcel_id}: ${label}`, { permanent: true, direction: "top", className: "epi-act" }).addTo(g);
      return () => clear();
    }
    const by = new Map(res.parcels.map((p) => [p.parcel_id, p]));
    const toward = (res.wind.from_deg + 180) % 360;
    const peak = (p?: { timeline?: number[] }) => Math.max(1, ...(p?.timeline ?? [0]));
    const maxArea = Math.max(0.0001, ...VILLAGE_PARCELS.filter((v) => v.id === s.parcel_id || (by.get(v.id)?.crop === s.crop && (by.get(v.id)?.distance_m ?? 1e9) <= res.disease.max_m)).map((v) => v.areaHa));
    const maxExp = Math.max(0.0001, ...res.parcels.filter((p) => p.crop === s.crop && p.distance_m <= res.disease.max_m).map((p) => areaOf(p.parcel_id) * peak(p) / 100));
    // illustrative plume: grows downwind with the hours
    const len = res.disease.max_m * Math.max(0.05, hour / 72);
    const fan = [[s.lat, s.lon] as [number, number], ...[-26, -13, 0, 13, 26].map((a) => dest(s.lat, s.lon, toward + a, len))];
    L.polygon(fan, { color: "#38bdf8", weight: 1, dashArray: "4 4", fillColor: "#38bdf8", fillOpacity: 0.14, interactive: false }).addTo(g);
    VILLAGE_PARCELS.forEach((v) => {
      const p = by.get(v.id);
      const isSrc = v.id === s.parcel_id;
      if (!isSrc && !(p && p.crop === s.crop && p.distance_m <= res.disease.max_m)) return;
      const risk = isSrc ? 100 : effAt(p, hour, actAt);
      const lvl = isSrc ? "src" : levelOf(risk);
      let color = isSrc ? "#a855f7" : COLORS[lvl];
      if (econ && !isSrc) { const ratio = (v.areaHa * risk / 100) / maxExp; color = ratio < 0.33 ? "#facc15" : ratio < 0.66 ? "#f97316" : "#dc2626"; }
      L.polygon(v.coords, { color, weight: isSrc ? 5 : lvl === "red" || lvl === "amber" ? 4 : 2, fillColor: color, fillOpacity: isSrc ? 0.6 : 0.2 + Math.min(0.55, risk / 140), className: isSrc ? "epi-pulse" : "" })
        .bindTooltip(isSrc ? `${v.id}: infected (${s.disease})` : `${risk >= res.threshold ? "⚠ INSPECT NOW · " : ""}${v.id}: risk ${risk.toFixed(0)} at hour ${hour} · ${v.areaHa.toFixed(2)} ha${p?.hours_to_threshold ? ` · crosses ${res.threshold} at about hour ${p.hours_to_threshold}` : ""}`,
          risk >= res.threshold && !isSrc ? { permanent: true, direction: "top", className: "epi-act" } : { sticky: true })
        .addTo(g);
      // harvest bar: height = what is left of this parcel's projected harvest (area × (1 − loss share × risk))
      if (bars) {
        const area = v.areaHa, left = area * (1 - (lossPct / 100) * (risk / 100)), pct = Math.round((left / area) * 100);
        const H = Math.max(4, Math.round((left / maxArea) * 70)), lost = 1 - left / area;
        const c = lost < 0.08 ? "#22c55e" : lost < 0.2 ? "#a3e635" : lost < 0.3 ? "#f59e0b" : "#ef4444";
        const hitNow = !isSrc && p?.hours_to_threshold && hour >= p.hours_to_threshold && hour - p.hours_to_threshold < 1.5 && !(actAt !== null && p.hours_to_threshold > actAt);
        const sprayed = !isSrc && actAt !== null && !!p?.hours_to_threshold && p.hours_to_threshold > actAt;
        const burst = hitNow ? [0, 1, 2, 3, 4, 5].map((k) => `<i style="position:absolute;left:3px;top:-2px;width:3px;height:3px;background:#ef4444;animation:epi-burst .6s ease-out forwards;--dx:${Math.round(Math.cos(k * 1.05) * 26)}px;--dy:${Math.round(-12 - Math.abs(Math.sin(k * 1.05)) * 22)}px"></i>`).join("") : "";
        const html = `<div title="${v.id}: ${pct}% of projected harvest left${sprayed ? " (protected by acting early)" : ""}" style="position:relative;width:10px;height:${H}px;border-radius:2px 2px 0 0;background:linear-gradient(to right,${c},rgba(255,255,255,.35) 45%,${c});box-shadow:0 0 7px ${c},inset -2px 0 rgba(0,0,0,.35);transition:height .3s">${sprayed ? '<b style="position:absolute;top:-13px;left:-2px;font-size:11px">🛡</b>' : ""}${burst}</div>`;
        L.marker(CENTROIDS.get(v.id) ?? [v.lat, v.lon], { keyboard: false, icon: L.divIcon({ className: "", iconSize: [10, H], iconAnchor: [-14, H], html }) }).addTo(g);
      }
      // countdown ring: how much of the 72-hour window is left before this parcel's risk passes the threshold
      if (!isSrc && p?.hours_to_threshold && risk < res.threshold) {
        const left = Math.max(0, p.hours_to_threshold - hour), frac = Math.min(1, left / 72), urgent = left < 6;
        const html = `<svg width="46" height="46" viewBox="-23 -23 46 46" style="${urgent ? "animation:epi-blink .7s infinite" : ""}"><circle r="18" fill="rgba(0,0,0,.45)" stroke="#475569" stroke-width="3"/><circle r="18" fill="none" stroke="${urgent ? "#ef4444" : "#f59e0b"}" stroke-width="4" stroke-linecap="round" pathLength="100" stroke-dasharray="${(frac * 100).toFixed(1)} 100" transform="rotate(-90)"/><text y="4" text-anchor="middle" font-size="11" font-weight="700" fill="#fff">${left}h</text></svg>`;
        L.marker(CENTROIDS.get(v.id) ?? [v.lat, v.lon], { interactive: false, icon: L.divIcon({ className: "", iconSize: [46, 46], iconAnchor: [23, 23], html }) }).addTo(g);
      }
    });
    // wind arrows around the source
    [[-1, -1], [1, -1], [-1, 1], [1, 1]].forEach(([a, b]) => {
      const north = dest(s.lat, s.lon, 0, a * 450);
      const spot = dest(north[0], north[1], 90, b * 450);
      L.marker(spot, { interactive: false, icon: L.divIcon({ className: "", iconSize: [26, 26], html: `<div style="transform:rotate(${toward - 90}deg);font-size:22px;color:#38bdf8;text-shadow:0 0 4px #000">➤</div>` }) }).addTo(g);
    });
    return () => clear();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, res, hour, getMap, clear, econ, replay, bars, lossPct, actAt]);

  useEffect(() => () => clear(), [clear]);

  // optional spoken alert (browser speech, free): Tamil if the device has a Tamil voice, otherwise English
  useEffect(() => {
    if (!res || !voice || !playing || typeof window === "undefined" || !("speechSynthesis" in window)) return;
    const crossed = res.parcels.filter((p) => p.crop === res.source.crop && p.hours_to_threshold && p.hours_to_threshold <= hour && !(actAt !== null && p.hours_to_threshold > actAt)).sort((a, b) => (a.hours_to_threshold ?? 0) - (b.hours_to_threshold ?? 0));
    if (crossed.length > spoken.current) {
      const id = crossed[spoken.current].parcel_id;
      const ta = window.speechSynthesis.getVoices().find((v) => v.lang.toLowerCase().startsWith("ta"));
      const u = new SpeechSynthesisUtterance(ta ? `கிராம அறிவிப்பு. வயல் ${id} ஆபத்தான நிலையில் உள்ளது. இன்றே இலைகளைப் பரிசோதிக்கவும்.` : `Village alert. Parcel ${id} is at risk. Inspect the leaves today.`);
      u.lang = ta ? "ta-IN" : "en-IN"; if (ta) u.voice = ta;
      window.speechSynthesis.speak(u);
    }
    spoken.current = crossed.length;
  }, [hour, voice, playing, res, acted, actHour]);
  useEffect(() => { if (hour === 0) spoken.current = 0; }, [hour]);

  function start() {
    setReplay(null);
    const map = getMap();
    const go = (r: Res) => {
      if (map) {
        const ids = new Set([r.source.parcel_id, ...r.parcels.filter((p) => p.crop === r.source.crop && p.distance_m <= r.disease.max_m).map((p) => p.parcel_id)]);
        const pts = VILLAGE_PARCELS.filter((v) => ids.has(v.id)).flatMap((v) => v.coords);
        if (pts.length) map.fitBounds(L.latLngBounds(pts).pad(0.25), { maxZoom: 16, animate: true, paddingTopLeft: [30, 30], paddingBottomRight: [30, 200] });   // while playing the panel shrinks to a small bar, so keep parcels clear of it
      }
      setHour(0);
      setMini(true);
      setPlaying(true);
    };
    if (res) go(res);
    else void load(src).then((r) => r && go(r));
  }

  const live = res?.parcels.filter((p) => p.crop === res.source.crop && p.distance_m <= res.disease.max_m).map((p) => ({ ...p, now: effAt(p, hour, actAt) })).sort((a, b) => b.now - a.now) ?? [];
  const events = res ? res.parcels.filter((p) => p.crop === res.source.crop && p.hours_to_threshold && !(actAt !== null && p.hours_to_threshold > actAt)).sort((a, b) => (a.hours_to_threshold ?? 0) - (b.hours_to_threshold ?? 0)) : [];
  const done = events.filter((e) => (e.hours_to_threshold ?? 99) <= hour);
  const next = events.find((e) => (e.hours_to_threshold ?? 99) > hour);
  const harvest = (h: number, act: number | null) => {
    if (!res) return { potential: 0, lost: 0, protectedHa: 0 };
    const rows = res.parcels.filter((p) => p.crop === res.source.crop && p.distance_m <= res.disease.max_m);
    let potential = areaOf(res.source.parcel_id), lost = areaOf(res.source.parcel_id) * (lossPct / 100), protectedHa = 0;
    rows.forEach((p) => { const a = areaOf(p.parcel_id); potential += a; lost += a * (lossPct / 100) * effAt(p, h, act) / 100; if (act !== null && p.hours_to_threshold && p.hours_to_threshold > act) protectedHa += a; });
    return { potential, lost, protectedHa };
  };
  const hNo = harvest(hour, null), hAct = harvest(hour, actHour), kgMult = Number(kgHa) > 0 ? Number(kgHa) : 0;
  const unit = (ha: number) => (kgMult ? `${Math.round(ha * kgMult).toLocaleString("en-IN")} kg` : `${ha.toFixed(2)} ha-eq`);
  const avoided = hNo.lost - hAct.lost, sprayCost = Number(spray) > 0 ? Number(spray) * hAct.protectedHa : 0;
  const roi = mult && sprayCost ? (avoided * mult) / sprayCost : null;
  const harvestBox = res && (
    <div className="mt-1.5 rounded-lg border border-border p-1.5 text-[10.5px]" data-testid="epidemic-harvest">
      <div className="flex flex-wrap items-center gap-1.5">
        <button type="button" onClick={() => setBars((v) => !v)} aria-pressed={bars} className={`rounded-full border px-2 py-1 ${bars ? "border-primary bg-primary text-primary-foreground" : "border-border"}`}>🌾 Harvest bars</button>
        <button type="button" onClick={() => { setActed((v) => !v); setPlaying(false); setHour(0); }} aria-pressed={acted} className={`rounded-full border px-2 py-1 ${acted ? "border-primary bg-primary text-primary-foreground" : "border-border"}`}>{acted ? `Run 2: acted at hour ${actHour}` : "Run 1: no action"}</button>
        <select value={actHour} onChange={(e) => { setActHour(Number(e.target.value)); setHour(0); }} className="rounded border border-border bg-background px-1 py-0.5" aria-label="Hour of action">{[6, 12, 24, 36].map((h) => <option key={h} value={h}>act at h{h}</option>)}</select>
      </div>
      <p className="mt-1 font-semibold">Projected harvest here: {unit(hNo.potential)}</p>
      <p>No action, lost by hour {hour}: <b className="text-destructive">{unit(hNo.lost)}</b> ({hNo.potential ? Math.round((hNo.lost / hNo.potential) * 100) : 0}%)</p>
      <p>Acting at hour {actHour}: <b className="text-success">{unit(hAct.lost)}</b> lost; kept: <b>{unit(Math.max(0, avoided))}</b></p>
      {roi !== null && <p className="font-semibold">Prevention return: about {roi.toFixed(0)}x (your figures)</p>}
      <label className="mt-1 flex flex-wrap items-center gap-1">If untreated, an infected parcel loses
        <input type="number" min={5} max={90} value={lossPct} onChange={(e) => setLossPct(Math.min(90, Math.max(5, Number(e.target.value) || 30)))} className="w-12 rounded border border-border bg-background px-1 py-0.5" />% <span className="text-muted-foreground">(scenario assumption, set your own)</span>
      </label>
      <label className="mt-0.5 flex flex-wrap items-center gap-1">Yield kg/ha <input value={kgHa} onChange={(e) => setKgHa(e.target.value.replace(/[^0-9]/g, ""))} inputMode="numeric" placeholder="optional" className="w-16 rounded border border-border bg-background px-1 py-0.5" />
        Spray cost ₹/ha <input value={spray} onChange={(e) => setSpray(e.target.value.replace(/[^0-9]/g, ""))} inputMode="numeric" placeholder="optional" className="w-16 rounded border border-border bg-background px-1 py-0.5" />
        <span className="text-muted-foreground">(with ₹ value/ha above, shows the return)</span></label>
      <p className="mt-1 text-muted-foreground">Bars: area × (1 − loss share × risk), for the scanned parcels only. Acting early is assumed to hold a parcel's risk at its level then (not a measured spray effect). Dummy parcels; not a yield forecast.</p>
    </div>
  );
  const rp = replay?.data?.reconstruction?.best;
  const rIdx = replay && replay.data.history ? replay.data.history.series.now_i - replay.ago : -1;
  const rT = rIdx >= 0 ? replay?.data.history.series.T[rIdx] : null, rRH = rIdx >= 0 ? replay?.data.history.series.RH[rIdx] : null;
  const rPhase = !replay || !rp ? "" : replay.ago > rp.hours_ago_at_start ? "healthy" : replay.ago > rp.hours_ago_at_start - rp.hours ? "window" : replay.ago > (replay.data.reconstruction.symptom_noted_days_ago || 0) * 24 ? "incubating" : "symptoms";
  const replayText = !replay || !rp ? "" : `${replay.ago === 0 ? "Today" : `${(replay.ago / 24).toFixed(1)} days ago`}${rT != null ? ` · ${rT} °C, ${rRH}% humidity` : ""}. ` + (
    rPhase === "healthy" ? "The parcel is still healthy." :
    rPhase === "window" ? `WEATHER WINDOW OPEN: conditions suited ${replay.data.source.disease.toLowerCase()} (${rp.hours} h in a row). A preventive step would have been timely now. This is a reconstruction from weather history, not proof.` :
    rPhase === "incubating" ? "Infection is likely under way but not visible yet." : `Symptoms recorded. The early window was ${(rp.hours_ago_at_start / 24).toFixed(1)} days before today.`);
  const expo = res ? res.parcels.filter((p) => p.crop === res.source.crop && p.distance_m <= res.disease.max_m).reduce((a, p) => a + areaOf(p.parcel_id) * effAt(p, hour, actAt) / 100, 0) : 0;
  const expoText = mult ? `Exposure now: ₹${Math.round(expo * mult).toLocaleString("en-IN")} (area × risk × your ₹/ha)` : `Exposure now: ${expo.toFixed(2)} ha-equivalent (area × risk)`;
  const narration = replay ? replayText : !res ? "" : hour === 0
    ? `Hour 0: ${res.source.disease} is recorded on ${res.source.parcel_id}. Spores travel with the wind from the ${res.wind.from_compass}.`
    : done.length
      ? `Hour ${hour}: ${done.map((d) => d.parcel_id).join(", ")} now above ${res.threshold}. What to do: inspect leaves today, keep the field drained, ask the officer or KVK about a preventive spray.${next ? ` Next: ${next.parcel_id} at about hour ${next.hours_to_threshold}.` : ""}`
      : `Hour ${hour}: spores are drifting downwind; no parcel has crossed ${res.threshold} yet${next ? ` (first expected: ${next.parcel_id}, about hour ${next.hours_to_threshold})` : ""}. Keep watching.`;
  const field = "rounded-md border border-border bg-background px-2 py-1";

  return (
    <div className="pointer-events-auto relative">
      <button type="button" onClick={() => setOpen((o) => !o)} aria-pressed={open} aria-label="Epidemic forecast" title="Epidemic forecast: what to prevent, and a 72-hour live spread demo"
        className={`grid size-10 place-items-center rounded-lg border shadow-xl backdrop-blur-xl ${open ? "border-primary bg-primary text-primary-foreground" : "border-border bg-overlay/90 text-foreground hover:bg-accent"}`}>
        <Bug className="size-5" />
      </button>
      {open && res && (hour > 0 || playing || replay) && (
        <div className="pointer-events-none fixed left-1/2 top-3 z-40 w-[min(520px,calc(100vw-24px))] -translate-x-1/2 rounded-xl border border-border bg-overlay/90 p-2.5 text-xs text-foreground shadow-2xl backdrop-blur-md" data-testid="epidemic-narration">
          <div className="flex items-start gap-3"><Compass from={windFrom} speed={res.wind.mean_speed_kmh} /><p className="font-medium">{narration}</p></div>
        </div>
      )}
      {open && mini && legend && (
        <div className="pointer-events-auto fixed right-3 top-24 z-40 w-[min(250px,calc(100vw-24px))] rounded-xl border border-border bg-overlay/90 p-2.5 text-[10.5px] text-foreground shadow-2xl backdrop-blur-md" data-testid="epidemic-legend">
          <div className="mb-1 flex items-center justify-between"><b className="text-xs">What you are seeing</b><button type="button" onClick={() => setLegend(false)} aria-label="Hide legend" className="rounded p-0.5 hover:bg-accent"><X className="size-3.5" /></button></div>
          <ul className="grid gap-1">
            <li><span style={{ color: "#a855f7" }}>⬣</span> <b>Purple pulsing parcel</b>: the infected field (recorded disease).</li>
            <li><span style={{ color: "#fb923c" }}>●●●</span> <b>Orange dots on curved lines</b>: spores carried by the wind from the infected field to a neighbour. Thicker line and more dots = higher risk; red = past the threshold.</li>
            <li><span style={{ color: "#38bdf8" }}>➤</span> <b>Blue arrows and fan</b>: which way the wind blows and how far spores can reach (illustrative).</li>
            <li><span style={{ color: "#f59e0b" }}>◔</span> <b>Ring with hours</b>: time left before that parcel's risk passes the threshold; red blinking under 6 h.</li>
            <li><span style={{ color: "#ef4444" }}>■</span> <b>Red "INSPECT NOW"</b>: risk is past the threshold; check leaves today.</li>
            <li><span style={{ color: "#22c55e" }}>▮</span> <b>Glowing column</b>: harvest left on that parcel; it shrinks and reddens as risk grows. 🛡 = protected by acting early (Run 2).</li>
            <li className="text-muted-foreground">The yellow sun arc with an orange ball is the sun-path layer, not part of this demo; Focus hides it and the sun panels.</li>
          </ul>
          <p className="mt-1 text-muted-foreground">Scenario model on dummy parcels, not a validated forecast.</p>
        </div>
      )}
      {open && mini && !legend && (
        <button type="button" onClick={() => setLegend(true)} className="pointer-events-auto fixed right-3 top-24 z-40 rounded-full border border-border bg-overlay/90 px-2.5 py-1 text-[10.5px] shadow-xl">? What am I seeing</button>
      )}
      {open && mini && (
        <div className="absolute bottom-12 left-0 z-40 w-[min(330px,calc(100vw-24px))] rounded-xl border border-border bg-overlay/80 p-2.5 text-xs text-foreground shadow-2xl backdrop-blur-md" data-testid="epidemic-mini">
          <div className="flex items-center gap-2">
            {!playing ? (
              <button type="button" onClick={() => { if (hour >= 72) setHour(0); setPlaying(true); }} className="grid size-8 place-items-center rounded-lg bg-primary text-primary-foreground" aria-label="Play"><Play className="size-4" /></button>
            ) : (
              <button type="button" onClick={() => setPlaying(false)} className="grid size-8 place-items-center rounded-lg border border-border" aria-label="Pause"><Pause className="size-4" /></button>
            )}
            <button type="button" onClick={() => { setPlaying(false); setReplayPlaying(false); setReplay(null); setHour(0); }} className="grid size-8 place-items-center rounded-lg border border-border" aria-label="Reset"><RotateCcw className="size-3.5" /></button>
            <span className="font-mono text-[11px]">h {hour}/72</span>
            <div className="ml-auto flex gap-1" aria-label="Demo speed">
              {[0.5, 1, 2, 4].map((r) => <button key={r} type="button" onClick={() => setRate(r)} className={`rounded px-1.5 py-0.5 text-[10.5px] ${rate === r ? "bg-primary text-primary-foreground" : "border border-border"}`}>{r}x</button>)}
            </div>
            <button type="button" onClick={() => setMini(false)} className="rounded border border-border px-1.5 py-0.5 text-[10.5px]">Details</button>
            <button type="button" onClick={() => { setOpen(false); setPlaying(false); setMini(false); clear(); }} aria-label="Close" className="rounded p-1 hover:bg-accent"><X className="size-3.5" /></button>
          </div>
          <input type="range" min={0} max={72} value={hour} onChange={(e) => { setPlaying(false); setHour(Number(e.target.value)); }} className="mt-1.5 w-full" aria-label="Hours from now" />
          <label className="mt-0.5 flex items-center gap-2">Wind {speed} km/h
            <input type="range" min={0} max={30} value={speed} onChange={(e) => changeSpeed(Number(e.target.value))} className="flex-1" />
          </label>
                    {res && <p className="mt-1 text-[10.5px]">Lost by h{hour}: no action <b className="text-destructive">{unit(hNo.lost)}</b> · acting at h{actHour} <b className="text-success">{unit(hAct.lost)}</b></p>}
          <div className="mt-1 flex gap-1.5">
            <button type="button" onClick={() => setFocus((v) => !v)} aria-pressed={focus} className={`rounded-full border px-2 py-0.5 text-[10.5px] ${focus ? "border-primary bg-primary text-primary-foreground" : "border-border"}`}>🎬 Focus</button>
            <button type="button" onClick={() => setBars((v) => !v)} aria-pressed={bars} className={`rounded-full border px-2 py-0.5 text-[10.5px] ${bars ? "border-primary bg-primary text-primary-foreground" : "border-border"}`}>🌾 Bars</button>
            <button type="button" onClick={() => { setActed((v) => !v); setPlaying(false); setHour(0); }} aria-pressed={acted} className={`rounded-full border px-2 py-0.5 text-[10.5px] ${acted ? "border-primary bg-primary text-primary-foreground" : "border-border"}`}>{acted ? `Run 2: act at h${actHour}` : "Run 1: no action"}</button>
          </div>
          <details className="mt-1"><summary className="cursor-pointer text-[10.5px] text-primary">More: replay, money, wind, assumptions</summary>
<div className="mt-1.5 flex flex-wrap items-center gap-1.5">
            <button type="button" onClick={() => void startReplay()} className="rounded-full border border-primary/50 bg-primary/10 px-2 py-1 text-[10.5px] font-medium text-primary" data-testid="epidemic-replay">⏮ Show what could have been</button>
            <button type="button" onClick={() => setEcon((v) => !v)} aria-pressed={econ} className={`rounded-full border px-2 py-1 text-[10.5px] ${econ ? "border-primary bg-primary text-primary-foreground" : "border-border"}`}>{econ ? "₹ Money at stake" : "🌿 Disease risk"}</button>
            <button type="button" onClick={() => { setVoice((v) => !v); if (typeof window !== "undefined" && "speechSynthesis" in window) window.speechSynthesis.getVoices(); }} aria-pressed={voice} className={`rounded-full border px-2 py-1 text-[10.5px] ${voice ? "border-primary bg-primary text-primary-foreground" : "border-border"}`}>{voice ? "🔊 Voice alert on" : "🔈 Voice alert off"}</button>
          </div>
          {err && <p className="mt-1 text-[10.5px] text-destructive">{err}</p>}
          {econ && res && (
            <div className="mt-1.5 rounded-lg border border-border p-1.5 text-[10.5px]">
              <label className="flex items-center gap-1">Value of crop per ha (₹, you enter it)
                <input value={perHa} onChange={(e) => setPerHa(e.target.value.replace(/[^0-9]/g, ""))} inputMode="numeric" placeholder="e.g. your own figure" className="w-24 rounded border border-border bg-background px-1 py-0.5" />
              </label>
              <p className="mt-0.5 font-semibold">{expoText}</p>
              <p className="text-muted-foreground"><span style={{ color: "#facc15" }}>■</span> low &nbsp;<span style={{ color: "#f97316" }}>■</span> medium &nbsp;<span style={{ color: "#dc2626" }}>■</span> high share of this scan's largest exposure. Area-weighted exposure, not a loss forecast.</p>
            </div>
          )}
          {harvestBox}
          {res && <div className="mt-1"><Compass from={windFrom} speed={res.wind.mean_speed_kmh} onDrag={changeDir} /></div>}
          </details>
          {res && (
            <p className="mt-1 flex flex-wrap gap-x-3 font-mono text-[10.5px]">
              {live.slice(0, 3).map((p) => <span key={p.parcel_id}><b>{p.parcel_id}</b> <span style={{ color: COLORS[levelOf(p.now)] }}>{p.now.toFixed(0)}</span></span>)}
            </p>
          )}
        </div>
      )}
      {open && !mini && (
        <div className="absolute bottom-12 left-0 z-40 w-[min(380px,calc(100vw-24px))] max-h-[70vh] overflow-auto rounded-xl border border-border bg-overlay/95 p-3 text-xs text-foreground shadow-2xl backdrop-blur-xl" data-testid="epidemic-panel">
          <div className="mb-2 flex items-start justify-between gap-2">
            <div>
              <p className="text-sm font-semibold">Epidemic forecast</p>
              <p className="text-[10.5px] text-muted-foreground">Scenario model on dummy parcels. It ranks which neighbouring parcels may be exposed in 72 hours; it is not a validated forecast.</p>
            </div>
            <button type="button" onClick={() => { setOpen(false); setPlaying(false); setMini(false); clear(); }} aria-label="Close" className="rounded p-1 hover:bg-accent"><X className="size-4" /></button>
          </div>

          <div className="grid gap-2">
            <label className="grid gap-0.5">Infected parcel
              <select className={field} value={src} onChange={(e) => { setSrc(e.target.value); setPlaying(false); setHour(0); void load(e.target.value); }}>
                {srcs.map((s) => <option key={s.parcel_id} value={s.parcel_id}>{s.parcel_id} · {s.issue} ({s.neighbours_in_reach} neighbours)</option>)}
              </select>
            </label>
            <div className="grid grid-cols-[1fr_1fr] gap-2">
              <label className="grid gap-0.5">Wind from
                <select className={field} value={DIRS.some(([, d]) => d === dir) ? dir : -2} onChange={(e) => { const d = Number(e.target.value); setDir(d); setPlaying(false); setHour(0); void load(src, d, speed, fav); }}>
                  {DIRS.map(([n, d]) => <option key={n} value={d}>{n}</option>)}
                  {!DIRS.some(([, d]) => d === dir) && <option value={-2} disabled>dragged: {compassName(dir)}</option>}
                </select>
              </label>
              <label className="grid gap-0.5">Speed {speed} km/h
                <input type="range" min={0} max={30} value={speed} onChange={(e) => changeSpeed(Number(e.target.value))} />
              </label>
            </div>
            <label className="flex items-center gap-1"><input type="checkbox" checked={fav} onChange={(e) => { setFav(e.target.checked); setPlaying(false); setHour(0); void load(src, dir, speed, e.target.checked); }} /> assume favourable weather for the demo</label>
          </div>

          <div className="mt-3 flex items-center gap-2">
            {!playing ? (
              <button type="button" onClick={start} disabled={busy || !src} className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-4 py-2 font-semibold text-primary-foreground disabled:opacity-50" data-testid="epidemic-start">
                <Play className="size-4" /> {hour > 0 && hour < 72 ? "Resume" : "Start"} live demo
              </button>
            ) : (
              <button type="button" onClick={() => setPlaying(false)} className="inline-flex items-center gap-1.5 rounded-lg border border-border px-4 py-2 font-semibold"><Pause className="size-4" /> Pause</button>
            )}
            <button type="button" onClick={() => { setPlaying(false); setReplayPlaying(false); setReplay(null); setHour(0); }} className="inline-flex items-center gap-1 rounded-lg border border-border px-3 py-2"><RotateCcw className="size-3.5" /> Reset</button>
            <span className="ml-auto flex items-center gap-1">
              {[0.5, 1, 2, 4].map((r) => <button key={r} type="button" onClick={() => setRate(r)} aria-label={`Demo speed ${r}x`} className={`rounded px-1.5 py-0.5 text-[10.5px] ${rate === r ? "bg-primary text-primary-foreground" : "border border-border"}`}>{r}x</button>)}
              <span className="ml-1 font-mono text-[11px]">h {hour}/72</span>
            </span>
          </div>
          <input type="range" min={0} max={72} value={hour} onChange={(e) => { setPlaying(false); setHour(Number(e.target.value)); }} className="mt-1 w-full" aria-label="Hours from now" />
          <div className="mt-2 flex flex-wrap items-center gap-1.5">
            <button type="button" onClick={() => void startReplay()} className="rounded-full border border-primary/50 bg-primary/10 px-2 py-1 text-[10.5px] font-medium text-primary" data-testid="epidemic-replay-full">⏮ Show what could have been</button>
            <button type="button" onClick={() => setEcon((v) => !v)} aria-pressed={econ} className={`rounded-full border px-2 py-1 text-[10.5px] ${econ ? "border-primary bg-primary text-primary-foreground" : "border-border"}`}>{econ ? "₹ Money at stake" : "🌿 Disease risk"}</button>
            <button type="button" onClick={() => { setVoice((v) => !v); if (typeof window !== "undefined" && "speechSynthesis" in window) window.speechSynthesis.getVoices(); }} aria-pressed={voice} className={`rounded-full border px-2 py-1 text-[10.5px] ${voice ? "border-primary bg-primary text-primary-foreground" : "border-border"}`}>{voice ? "🔊 Voice alert on" : "🔈 Voice alert off"}</button>
          </div>
          {econ && res && (
            <div className="mt-1.5 rounded-lg border border-border p-1.5 text-[10.5px]">
              <label className="flex items-center gap-1">Value of crop per ha (₹, you enter it)
                <input value={perHa} onChange={(e) => setPerHa(e.target.value.replace(/[^0-9]/g, ""))} inputMode="numeric" placeholder="e.g. your own figure" className="w-24 rounded border border-border bg-background px-1 py-0.5" />
              </label>
              <p className="mt-0.5 font-semibold">{expoText}</p>
              <p className="text-muted-foreground"><span style={{ color: "#facc15" }}>■</span> low &nbsp;<span style={{ color: "#f97316" }}>■</span> medium &nbsp;<span style={{ color: "#dc2626" }}>■</span> high share of this scan's largest exposure. Area-weighted exposure, not a loss forecast.</p>
            </div>
          )}
          {harvestBox}
          {err && <p className="mt-1 text-destructive">{err}</p>}

          {res && (
            <>
              <div className="mt-2"><Compass from={windFrom} speed={res.wind.mean_speed_kmh} onDrag={changeDir} /></div>
              <p className="mt-2 rounded-lg border border-primary/40 bg-primary/10 p-2 font-medium" data-testid="epidemic-now">{narration}</p>
              <p className="mt-2 font-semibold">{res.source.disease} on {res.source.parcel_id}: wind from the {res.wind.from_compass}, {res.wind.mean_speed_kmh} km/h</p>
              <ul className="mt-1 grid gap-1">
                {live.slice(0, 6).map((p) => (
                  <li key={p.parcel_id} className="grid grid-cols-[48px_minmax(0,1fr)_96px] items-center gap-2">
                    <b>{p.parcel_id}</b>
                    <span className="h-2 overflow-hidden rounded-full bg-muted"><span className="block h-full rounded-full" style={{ width: `${Math.min(100, p.now)}%`, background: COLORS[levelOf(p.now)] }} /></span>
                    <span className="text-right font-mono text-[10.5px]">{p.now.toFixed(0)} {p.hours_to_threshold ? `· ~h${p.hours_to_threshold}` : ""}</span>
                  </li>
                ))}
              </ul>
              <p className="mt-1 text-[10.5px] text-muted-foreground">Risk 0 to 100 builds hour by hour from distance, wind direction and speed, and the disease's weather window. The blue fan is an illustrative spore reach, not a measurement.</p>
              <p className={`mt-1 text-[10.5px] ${res.verification.passed ? "text-success" : "text-destructive"}`}>{res.verification.passed ? "✅" : "⚠"} Geometry verifier (arithmetic): {res.verification.checked} flagged parcel(s) checked, {res.verification.failed.length} failed.</p>
            </>
          )}

          {prev && (
            <div className="mt-3 rounded-lg border border-border p-2.5" data-testid="epidemic-prevent">
              <p className="mb-1 font-semibold">What to do now: {prev.disease}</p>
              <ul className="list-disc space-y-0.5 pl-4">{prev.steps.map((s) => <li key={s}>{s}</li>)}</ul>
              {prev.tnau_passages.length > 0 && (
                <details className="mt-1.5">
                  <summary className="cursor-pointer text-primary">TNAU passages that mention it ({prev.tnau_passages.length})</summary>
                  <ul className="mt-1 grid gap-1.5">{prev.tnau_passages.map((t) => <li key={t.slice(0, 40)} className="rounded bg-muted/40 p-1.5 text-[10.5px]">{t}</li>)}</ul>
                </details>
              )}
              <p className="mt-1 text-[10px] text-muted-foreground">{prev.note}</p>
              <button type="button" onClick={() => window.dispatchEvent(new CustomEvent("cropsy-ask", { detail: prev.ask }))} className="mt-2 rounded-full border border-primary/50 bg-primary/10 px-3 py-1.5 font-medium text-primary">Ask Cropsy: {prev.ask}</button>
              <button type="button" onClick={() => window.dispatchEvent(new CustomEvent("cropsy-ask", { detail: `${res?.source.parcel_id ?? ""} village spread risk scan` }))} className="ml-2 mt-2 rounded-full border border-border px-3 py-1.5">Full scan in chat (alert in Tamil + English)</button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
