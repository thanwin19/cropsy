import { CalendarDays, ChevronDown, CloudSun, Moon, Pause, Play, RefreshCw, Sun, TriangleAlert } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import { useMediaQuery } from "../../lib/useMediaQuery";

const p2 = (n: number) => String(Math.floor(n)).padStart(2, "0");
export const hm = (m: number) => `${p2(m / 60)}:${p2(m % 60)}`;
export const hms = (m: number) => {
  const s = Math.round(m * 60);
  return `${p2(s / 3600)}:${p2((s % 3600) / 60)}:${p2(s % 60)}`;
};
export const dur = (m: number) => `${Math.floor(m / 60)}h ${p2(Math.round(m % 60))}m`;

/**
 * Map overlay panels, in the same look as the rest of the app: rounded cards on a translucent overlay surface, plain 11-12px text,
 * mono values, amber accents. Same data and controls as before; each panel can be dragged and collapsed.
 */
const PANEL = "pointer-events-auto relative z-20 rounded-xl border border-border bg-overlay/90 p-3 shadow-xl backdrop-blur-xl";

/** Panels start open on larger screens and collapsed on phones, where they would otherwise cover the whole map. */
function useCollapsed() {
  const narrow = useMediaQuery("(max-width: 639px)");
  const [open, setOpen] = useState(true);
  useEffect(() => {
    if (narrow) setOpen(false);
  }, [narrow]);
  return { open, narrow, toggle: () => setOpen((v) => !v) };
}

const Chevron = ({ open, label, onClick }: { open: boolean; label: string; onClick: () => void }) => (
  <button
    type="button"
    data-nodrag
    aria-expanded={open}
    aria-label={`${open ? "Collapse" : "Expand"} ${label}`}
    onClick={onClick}
    className="grid size-6 shrink-0 place-items-center rounded-md text-muted-foreground transition hover:bg-accent hover:text-foreground"
  >
    <ChevronDown className={`size-4 transition-transform ${open ? "rotate-180" : ""}`} />
  </button>
);

const KV = ({ k, v, hi }: { k: string; v: ReactNode; hi?: boolean }) => (
  <>
    <span className="text-muted-foreground">{k}</span>
    <b className={`font-mono font-medium ${hi ? "text-primary" : "text-foreground"}`}>{v}</b>
  </>
);

/* ── Dark / Satellite / Street ── */
export function MapTypeSwitch({ value, onChange }: { value: "dark" | "satellite" | "street"; onChange: (v: "dark" | "satellite" | "street") => void }) {
  return (
    <select
      aria-label="Map style"
      value={value}
      onChange={(e) => onChange(e.target.value as "dark" | "satellite" | "street")}
      className="pointer-events-auto h-9 cursor-pointer rounded-lg border-2 border-foreground/85 bg-transparent px-3 text-sm font-medium capitalize text-foreground outline-none focus-visible:ring-2 focus-visible:ring-primary"
    >
      {(["dark", "satellite", "street"] as const).map((b) => (
        <option key={b} value={b}>
          {b}
        </option>
      ))}
    </select>
  );
}

/* ── LEFT: Solar ephemeris ── */
export function SolarPanel(p: {
  parcels: readonly { id: string; crop: string; [key: string]: any }[];
  selId: string;
  onParcel: (id: string) => void;
  village: string;
  dateLabel: string;
  onDate: () => void;
  timeLabel: string;
  onNow: () => void;
  isLive: boolean;
  alt: number;
  az: number;
  compass: string;
  noon: number;
  dayMin: number;
  rise: number;
  set: number;
  golden: number;
  directStart: string;
  directEnd: string;
  demNote: string;
}) {
  const c = useCollapsed();
  return (
    <div
      id="then-malai-ephemeris-panel"
      className={`${PANEL} max-h-[calc(100vh-260px)] overflow-y-auto ${c.open ? "w-[218px]" : "w-auto"}`}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="flex items-center gap-2 text-xs font-semibold">
          <Sun className="size-4 text-primary" />
          {c.open || !c.narrow ? "Solar ephemeris" : "Solar"}
        </span>
        <span className="flex items-center gap-1">
          <button
            type="button"
            data-nodrag
            onClick={p.onNow}
            title="Jump to the current time"
            className="flex items-center gap-1 rounded-full border border-success/40 bg-success/10 px-2 py-0.5 font-mono text-[10px] text-success"
          >
            <span className={`size-1.5 rounded-full bg-success ${p.isLive ? "animate-pulse" : ""}`} />
            {p.timeLabel}
          </button>
          <Chevron open={c.open} label="solar ephemeris" onClick={c.toggle} />
        </span>
      </div>

      {c.open && (
        <div className="mt-3 grid grid-cols-2 gap-x-3 gap-y-2 text-[11px]">
          <span className="text-muted-foreground">Parcel</span>
          <label className="relative flex items-center justify-between gap-1 font-mono font-semibold">
            <span className="truncate">
              {p.selId} · {p.parcels.find((x) => x.id === p.selId)?.crop}
            </span>
            <ChevronDown className="size-3 shrink-0 text-muted-foreground" />
            <select data-nodrag value={p.selId} onChange={(e) => p.onParcel(e.target.value)} className="absolute inset-0 cursor-pointer opacity-0" aria-label="Parcel">
              {p.parcels.map((x) => (
                <option key={x.id} value={x.id}>
                  {x.id} • {x.crop}
                </option>
              ))}
            </select>
          </label>
          <span className="text-muted-foreground">Date</span>
          <button type="button" data-nodrag onClick={p.onDate} className="flex items-center justify-between gap-1 text-left font-mono font-semibold hover:text-primary">
            <span className="truncate">{p.dateLabel}</span>
            <CalendarDays className="size-3 shrink-0 text-muted-foreground" />
          </button>
          <KV k="Altitude" v={`${p.alt.toFixed(1)}°`} hi />
          <KV k="Azimuth" v={`${p.az.toFixed(1)}° ${p.compass}`} />
          <KV k="Culmination" v={hms(p.noon)} />
          <KV k="Daylight" v={dur(p.dayMin)} />
          <KV k="Sunrise" v={hms(p.rise)} hi />
          <KV k="Sunset" v={hms(p.set)} hi />
          <KV k="Golden hour" v={hms(p.golden)} />
          <KV k="Direct sun" v={`${p.directStart}–${p.directEnd}`} />
          <p className="col-span-2 mt-1 flex items-start gap-1.5 text-[10px] leading-snug text-muted-foreground">
            <TriangleAlert className="mt-px size-3 shrink-0 text-primary" />
            <span>
              {p.village} · {p.demNote}
            </span>
          </p>
        </div>
      )}
    </div>
  );
}

/* ── RIGHT: Shadow time (keeps a slider so shadowMin stays controllable) ── */
export function ShadowPanel(p: {
  shadowMin: number;
  onShadowMin: (m: number) => void;
  onDragStart: () => void;
  onDragEnd: () => void;
  status: "direct" | "shaded" | "night";
  startMin: number;
  cutoffMin: number;
  alt: number;
  az: number;
  horizon: number;
  obstructed: boolean;
  cloud: number;
  parcelId: string;
  onSync: () => void;
  observed?: ReactNode;
  headerExtra?: ReactNode;
}) {
  const prog = Math.min(1, Math.max(0, (p.shadowMin - p.startMin) / Math.max(1, p.cutoffMin - p.startMin)));
  const badge = {
    direct: "border-primary/40 bg-primary/10 text-primary",
    shaded: "border-destructive/40 bg-destructive/10 text-destructive",
    night: "border-border bg-muted text-muted-foreground",
  }[p.status];
  const c = useCollapsed();
  return (
    <div className={`${PANEL} ${c.open ? "w-[230px]" : "w-auto"}`}>
      <div className="flex items-center justify-between gap-2">
        <span className="flex items-center gap-2 text-xs font-semibold">
          <CloudSun className="size-4 text-primary" />
          {c.open || !c.narrow ? "Shadow time" : "Shadow"}
        </span>
        <span className="flex items-center gap-1">
          {(c.open || !c.narrow) && (
            <span className={`rounded-full border px-2 py-0.5 font-mono text-[10px] ${badge}`}>
              {p.status === "direct" ? "Direct sun" : p.status === "shaded" ? "Shaded" : "Night"}
            </span>
          )}
          {p.headerExtra}
          <Chevron open={c.open} label="shadow time" onClick={c.toggle} />
        </span>
      </div>

      {c.open && (
        <>
          <p className="mt-3 font-mono text-xl">
            {hm(p.shadowMin)} <span className="text-xs text-muted-foreground">IST</span>
          </p>
          <div className="relative mt-2 h-1.5 rounded-full bg-muted">
            <div className="h-full rounded-full bg-primary" style={{ width: `${prog * 100}%` }} />
            <input
              data-nodrag
              type="range"
              min={0}
              max={1439}
              value={p.shadowMin}
              aria-label="Shadow time"
              onChange={(e) => p.onShadowMin(+e.target.value)}
              onPointerDown={p.onDragStart}
              onPointerUp={p.onDragEnd}
              onPointerCancel={p.onDragEnd}
              className="absolute -inset-y-2 h-5 w-full cursor-pointer opacity-0"
            />
          </div>
          <div className="mt-1 flex justify-between font-mono text-[10px] text-muted-foreground">
            <span>{hm(p.startMin)} direct</span>
            <span>{hm(p.cutoffMin)} cutoff</span>
          </div>

          <div className="mt-3 space-y-1 text-[11px] text-muted-foreground">
            <p>
              Sun altitude <b className="font-mono text-foreground">{p.alt.toFixed(1)}°</b>
            </p>
            <p>
              Sun azimuth <b className="font-mono text-foreground">{p.az.toFixed(1)}°</b>
            </p>
            <p>
              Terrain horizon{" "}
              <b className={`font-mono ${p.obstructed ? "text-destructive" : "text-foreground"}`}>
                {p.horizon.toFixed(1)}°{p.obstructed ? "" : " (clear)"}
              </b>
            </p>
            <p>
              Cloud effect <b className="font-mono text-foreground">{Math.round(p.cloud)}%</b>
            </p>
          </div>

          {p.observed}

          <div className="mt-3 flex items-center justify-between border-t border-border pt-2">
            <button
              type="button"
              data-nodrag
              onClick={p.onSync}
              className="flex items-center gap-1.5 rounded-md border border-border bg-secondary px-2 py-1 text-[11px] text-secondary-foreground transition hover:bg-accent"
            >
              <RefreshCw className="size-3" /> Sync solar time
            </button>
            <span className="font-mono text-[10px] text-muted-foreground">{p.parcelId}</span>
          </div>
        </>
      )}
    </div>
  );
}

/* ── BOTTOM: 24 h time bar ── */
const pct = (m: number) => `${(m / 1440) * 100}%`;

export function SolarTimeline(p: {
  minutes: number;
  rise: number;
  set: number;
  isLive: boolean;
  playing: boolean;
  onTogglePlay: () => void;
  onNow: () => void;
  onScrub: (m: number) => void;
  onDragStart: () => void;
  onDragEnd: () => void;
}) {
  return (
    <div
      id="then-malai-horizontal-timeline-container"
      className="pointer-events-auto absolute bottom-3 left-1/2 z-20 w-[calc(100%-24px)] -translate-x-1/2 rounded-xl border border-border bg-overlay/90 p-2.5 shadow-xl backdrop-blur-xl sm:w-[min(640px,calc(100%-460px))] sm:min-w-[360px]"
    >
      <div className="grid grid-cols-[40px_minmax(0,1fr)_auto] items-center gap-3">
        <button
          type="button"
          data-nodrag
          aria-label={p.playing ? "Pause time" : "Play time"}
          onClick={p.onTogglePlay}
          className="grid size-10 place-items-center rounded-md bg-primary text-primary-foreground transition hover:bg-primary/90"
        >
          {p.playing ? <Pause className="size-4" /> : <Play className="size-4" />}
        </button>

        <div className="min-w-0">
          <div className="relative h-1.5 rounded-full bg-muted">
            <div className="absolute inset-y-0 rounded-full bg-primary" style={{ left: pct(p.rise), width: pct(p.set - p.rise) }} />
            <input
              data-nodrag
              type="range"
              min={0}
              max={1439}
              value={p.minutes}
              aria-label="Time of day"
              onChange={(e) => p.onScrub(+e.target.value)}
              onPointerDown={p.onDragStart}
              onPointerUp={p.onDragEnd}
              onPointerCancel={p.onDragEnd}
              className="absolute -inset-y-2 z-10 h-5 w-full cursor-pointer opacity-0"
            />
            <div
              className="pointer-events-none absolute top-1/2 size-3.5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-background bg-primary shadow-md"
              style={{ left: pct(p.minutes) }}
            />
          </div>
          <div className="mt-2 flex items-center justify-between font-mono text-[10px] text-muted-foreground">
            <span className="flex items-center gap-1">
              <Sun className="size-3 text-primary" /> {hm(p.rise)} sunrise
            </span>
            <button type="button" data-nodrag onClick={p.onNow} className="rounded px-1.5 py-0.5 hover:bg-accent hover:text-foreground">
              Now
            </button>
            <span className="flex items-center gap-1">
              <Moon className="size-3" /> sunset {hm(p.set)}
            </span>
          </div>
        </div>

        <div className="text-right">
          <p className="font-mono text-xs">{hm(p.minutes)} IST</p>
          <p className="text-[10px] text-muted-foreground">{p.isLive ? "live" : "manual"}</p>
        </div>
      </div>
    </div>
  );
}
