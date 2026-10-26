import React, { useState } from "react";
import { getApiSettings } from "@/lib/cropsy-api";
import { Badge, Card, Kv, SourceNote } from "./ui";

type PointValue = { name: string; month: string; units?: string; value?: number | string | null; rgb?: number[] };
type PointResponse = {
  inside: boolean; lat: number; lon: number; parcel_id?: string | null; note: string; values: Record<string, PointValue>;
};

interface Props {
  /** Lets the parent move its map to the looked-up point. */
  onFlyTo?: (lat: number, lon: number) => void;
  /** The latest point the user clicked on the map, if the parent tracks it. Enables the "use my map click" button. */
  clicked?: { lat: number; lon: number } | null;
}

const parse = (s: string): [number, number] | null => {
  const m = s.trim().match(/^(-?\d+(?:\.\d+)?)\s*[,\s]\s*(-?\d+(?:\.\d+)?)$/);
  if (!m) return null;
  const lat = Number(m[1]), lon = Number(m[2]);
  return Math.abs(lat) <= 90 && Math.abs(lon) <= 180 ? [lat, lon] : null;
};

const fmt = (v: PointValue) => {
  if (v.rgb) return `rgb(${v.rgb.join(", ")})`;
  if (v.value == null) return "no data here";
  return typeof v.value === "number" ? `${v.value}${v.units ? ` ${v.units.split(" ")[0] === "index" ? "" : v.units}` : ""}` : String(v.value);
};

/** Type a coordinate (or use the last map click) and read the value of every map layer there, plus the parcel it falls in. */
export const CoordinateLookup: React.FC<Props> = ({ onFlyTo, clicked }) => {
  const [text, setText] = useState("8.9105, 77.3210");
  const [res, setRes] = useState<PointResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const run = async (lat: number, lon: number) => {
    setBusy(true);
    setError(null);
    try {
      const base = (getApiSettings().baseUrl || "").replace(/\/$/, "");
      const r = await fetch(`${base}/api/point?lat=${lat}&lon=${lon}`, { headers: { Accept: "application/json" } });
      if (!r.ok) throw new Error(`Lookup failed (${r.status})`);
      const body = (await r.json()) as PointResponse;
      setRes(body);
      if (body.inside) onFlyTo?.(lat, lon);
    } catch (e: any) {
      setError(e?.message || "Lookup failed");
      setRes(null);
    } finally {
      setBusy(false);
    }
  };

  const go = () => {
    const p = parse(text);
    if (!p) { setError("Type latitude and longitude, for example 8.9105, 77.3210"); return; }
    run(p[0], p[1]);
  };

  return (
    <Card title="Coordinate lookup" eyebrow="Any point on the map">
      <div className="flex flex-wrap gap-2">
        <input
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && go()}
          aria-label="Latitude and longitude"
          placeholder="latitude, longitude"
          className="min-w-0 flex-1 rounded-lg border border-white/10 bg-black/25 px-3 py-1.5 font-mono text-xs text-foreground outline-none focus:border-primary/60"
        />
        <button onClick={go} disabled={busy} className="rounded-lg bg-primary px-3 py-1.5 text-xs font-semibold text-primary-foreground hover:opacity-90 disabled:opacity-50">
          {busy ? "Looking…" : "Look up"}
        </button>
        {clicked && (
          <button
            onClick={() => { setText(`${clicked.lat.toFixed(5)}, ${clicked.lon.toFixed(5)}`); run(clicked.lat, clicked.lon); }}
            className="rounded-lg border border-white/10 px-3 py-1.5 text-xs text-foreground hover:border-primary/60"
          >
            Use my map click
          </button>
        )}
      </div>

      {error && <p className="text-xs text-destructive">{error}</p>}

      {res && !res.inside && <p className="text-xs text-warning">{res.note}</p>}

      {res?.inside && (
        <div className="flex flex-col gap-2">
          <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
            <span className="font-mono text-foreground">{res.lat.toFixed(5)}, {res.lon.toFixed(5)}</span>
            {res.parcel_id ? <Badge tone="ok">inside parcel {res.parcel_id}</Badge> : <Badge tone="mute">not inside a parcel</Badge>}
          </div>
          <div>
            {Object.entries(res.values).map(([k, v]) => (
              <Kv
                key={k}
                k={`${v.name}${v.month !== "static" ? ` · ${v.month}` : ""}`}
                v={v.rgb ? <span className="inline-flex items-center gap-1.5"><i className="inline-block h-3 w-3 rounded-sm border border-white/20" style={{ background: `rgb(${v.rgb.join(",")})` }} />{fmt(v)}</span> : fmt(v)}
              />
            ))}
          </div>
          <SourceNote>{res.note}</SourceNote>
        </div>
      )}
    </Card>
  );
};

export default CoordinateLookup;
