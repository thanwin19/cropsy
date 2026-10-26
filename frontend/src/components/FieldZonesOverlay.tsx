import { useEffect, useRef, useState } from "react";
import L from "leaflet";
import { X } from "lucide-react";
import { getApiSettings } from "@/lib/cropsy-api";
import { VILLAGE_PARCELS } from "@/data/villageParcels.generated";

const base = () => (getApiSettings().baseUrl || "").replace(/\/$/, "");
const COLORS: Record<string, string> = { lower: "#ef4444", typical: "#a3a3a3", higher: "#22c55e", no_data: "#475569" };
type Cell = { name: string; class: string; mean: number | null; vs_parcel?: number; n_valid: number; ring: [number, number][] };
type Zones = { available: boolean; reason?: string; month: string; parcel_mean?: number; threshold?: number; n_valid?: number; cells: Cell[]; caution?: string; provenance?: { basis: string; resolution: string } };

/** Sutherland-Hodgman: clip a polygon (the parcel) to an axis-aligned rectangle (a grid cell), so each coloured cell stays inside the field boundary. Points are [x, y]. */
function clipRect(poly: [number, number][], x0: number, y0: number, x1: number, y1: number): [number, number][] {
  const edges: [(p: [number, number]) => boolean, (a: [number, number], b: [number, number]) => [number, number]][] = [
    [(p) => p[0] >= x0, (a, b) => [x0, a[1] + ((b[1] - a[1]) * (x0 - a[0])) / (b[0] - a[0])]],
    [(p) => p[0] <= x1, (a, b) => [x1, a[1] + ((b[1] - a[1]) * (x1 - a[0])) / (b[0] - a[0])]],
    [(p) => p[1] >= y0, (a, b) => [a[0] + ((b[0] - a[0]) * (y0 - a[1])) / (b[1] - a[1]), y0]],
    [(p) => p[1] <= y1, (a, b) => [a[0] + ((b[0] - a[0]) * (y1 - a[1])) / (b[1] - a[1]), y1]],
  ];
  let out = poly;
  for (const [inside, cross] of edges) {
    const inp = out;
    out = [];
    inp.forEach((cur, i) => {
      const prev = inp[(i + inp.length - 1) % inp.length];
      if (inside(cur)) {
        if (!inside(prev)) out.push(cross(prev, cur));
        out.push(cur);
      } else if (inside(prev)) out.push(cross(prev, cur));
    });
    if (!out.length) break;
  }
  return out;
}

/** Real pixel-level field zones from the satellite raster, drawn inside the selected parcel. Opened by the chat's "Show on map" button (event cropsy-zones). */
export function FieldZonesOverlay({ getMap }: { getMap: () => L.Map | null }) {
  const [pid, setPid] = useState("");
  const [z, setZ] = useState<Zones | null>(null);
  const [err, setErr] = useState("");
  const group = useRef<L.LayerGroup | null>(null);

  useEffect(() => {
    const h = (e: Event) => setPid(String((e as CustomEvent<string>).detail || ""));
    window.addEventListener("cropsy-zones", h);
    return () => window.removeEventListener("cropsy-zones", h);
  }, []);

  // while the zones are shown, the big sun-path arc is hidden so the field itself is visible
  useEffect(() => {
    if (!pid) return;
    document.body.classList.add("zones-focus");
    return () => document.body.classList.remove("zones-focus");
  }, [pid]);

  useEffect(() => {
    if (!pid) return;
    setErr("");
    setZ(null);
    fetch(`${base()}/api/field-health/${pid}`).then((r) => r.json()).then((d) => setZ(d.zones ?? null)).catch(() => setErr("Could not load the field zones"));
  }, [pid]);

  useEffect(() => {
    const map = getMap();
    group.current?.remove();
    group.current = null;
    if (!map || !z || !z.available) return;
    const v = VILLAGE_PARCELS.find((x) => x.id === pid);
    if (!v) return;
    const g = L.layerGroup().addTo(map);
    group.current = g;
    const parcel = v.coords.map(([lat, lon]) => [lon, lat] as [number, number]);
    z.cells.forEach((c) => {
      const xs = c.ring.map((p) => p[0]), ys = c.ring.map((p) => p[1]);
      const clipped = clipRect(parcel, Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys));
      if (clipped.length < 3) return;
      const col = COLORS[c.class] ?? "#a3a3a3";
      L.polygon(clipped.map(([lon, lat]) => [lat, lon] as [number, number]), { color: col, weight: c.class === "lower" ? 3 : 1, fillColor: col, fillOpacity: c.class === "lower" ? 0.5 : 0.22 })
        .bindTooltip(c.class === "no_data" ? `${c.name}: not enough clear pixels (${c.n_valid})` : `${c.name}: NDVI ${c.mean} (${(c.vs_parcel ?? 0) >= 0 ? "+" : ""}${c.vs_parcel} vs the field), ${c.n_valid} pixels · ${c.class}`, { sticky: true })
        .addTo(g);
    });
    L.polygon(v.coords, { color: "#fff", weight: 2, fill: false, dashArray: "4 3", interactive: false }).addTo(g);
    map.fitBounds(L.latLngBounds(v.coords).pad(1.2), { maxZoom: 18, animate: true });
    return () => { g.remove(); };
  }, [z, pid, getMap]);

  if (!pid) return null;
  const close = () => { setPid(""); setZ(null); };
  return (
    <div className="pointer-events-auto fixed left-3 top-20 z-40 w-[min(300px,calc(100vw-24px))] rounded-xl border border-border bg-overlay/95 p-2.5 text-[11px] text-foreground shadow-2xl backdrop-blur-md" data-testid="zones-panel">
      <div className="flex items-start justify-between gap-2">
        <b className="text-xs">Inside {pid}: NDVI zones</b>
        <button type="button" onClick={close} aria-label="Close" className="rounded p-0.5 hover:bg-accent"><X className="size-3.5" /></button>
      </div>
      {err && <p className="mt-1 text-destructive">{err}</p>}
      {z && !z.available && <p className="mt-1">Not available: {z.reason}. Cropsy will not guess.</p>}
      {z?.available && (
        <>
          <p className="mt-1">{z.month} composite · parcel mean {z.parcel_mean} · {z.n_valid} clear pixels (about 11 m)</p>
          <p className="mt-1 flex flex-wrap gap-x-3"><span style={{ color: COLORS.lower }}>■ lower</span><span style={{ color: COLORS.typical }}>■ typical</span><span style={{ color: COLORS.higher }}>■ higher</span><span style={{ color: COLORS.no_data }}>■ too few pixels</span></p>
          <p className="mt-1 text-muted-foreground">{z.caution}</p>
        </>
      )}
      {!z && !err && <p className="mt-1 text-muted-foreground">Loading…</p>}
    </div>
  );
}
