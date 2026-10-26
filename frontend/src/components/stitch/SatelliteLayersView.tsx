import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { fetchLayers, layerUrl, type LayerInfo, type LayersManifest } from "@/lib/cropsy-api";
import { COLORMAP_NAMES, gradientCss } from "@/lib/colormaps";
import { blend, colorize, decode, difference, plain, toUrl, valueAt, type Decoded } from "@/lib/rasterLayers";
import { VILLAGE_PARCELS } from "../../data/villageParcels.generated";
import { makeZoomDraggable } from "../../lib/dragZoomControl";
import { IndexResultsPanel } from "./IndexResultsPanel";
import { LayerPicker } from "./LayerPicker";
import { CoordinateLookup } from "./CoordinateLookup";
import { BulkExport } from "./BulkExport";
import { Badge, Card, Empty, PageHeader } from "./ui";

interface Props {
  selectedParcelId: string;
  onSelectParcel: (id: string) => void;
  onBackToChat: () => void;
}

const GROUPS = ["Crop health", "Water", "Soil", "Terrain and land", "Radar", "Display"];
const DEFAULT_CMAP: Record<string, string> = {
  ndvi: "RdYlGn", evi: "RdYlGn", savi: "RdYlGn", ndre: "RdYlGn", ndmi: "Blues", ndwi: "Blues", et: "Viridis",
  soc: "YlOrBr", dem: "Terrain", rvi: "Viridis", rsm: "Blues",
};
const GRAY = new Set(["ndvi", "evi", "savi", "ndre", "ndmi", "ndwi", "et", "soc", "dem", "rvi", "rsm"]);
const KIND_TEXT = { real: "real data", modelled: "modelled", derived: "our definition" } as const;
const KIND_TONE = { real: "ok", modelled: "warn", derived: "dummy" } as const;
const monthLabel = (m: string) => (m === "static" ? "single map" : new Date(m + "-15").toLocaleDateString("en-GB", { month: "short", year: "numeric" }));
const BASES = {
  satellite: { url: "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}", attr: "Esri World Imagery" },
  street: { url: "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", attr: "© OpenStreetMap" },
  dark: { url: "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", attr: "© CARTO" },
} as const;

function download(name: string, text: string, type: string) {
  const url = URL.createObjectURL(new Blob([text], { type }));
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  URL.revokeObjectURL(url);
}

function parcelsKml(): string {
  const marks = VILLAGE_PARCELS.map((p) => {
    const ring = [...p.coords, p.coords[0]].map(([lat, lon]) => `${lon},${lat},0`).join(" ");
    return `<Placemark><name>${p.id}</name><description>${p.crop} (${p.variety}), ${p.areaHa} ha. Crop, owner and issue are DUMMY data.</description>` +
      `<Polygon><outerBoundaryIs><LinearRing><coordinates>${ring}</coordinates></LinearRing></outerBoundaryIs></Polygon></Placemark>`;
  }).join("");
  return `<?xml version="1.0" encoding="UTF-8"?><kml xmlns="http://www.opengis.net/kml/2.2"><Document><name>Then Malai parcels</name>${marks}</Document></kml>`;
}

function parcelsGeoJson(): string {
  return JSON.stringify({
    type: "FeatureCollection",
    features: VILLAGE_PARCELS.map((p) => ({
      type: "Feature", id: p.id,
      properties: { parcel_id: p.id, crop: p.crop, variety: p.variety, area_ha: p.areaHa, note: "crop, owner and issue are dummy data" },
      geometry: { type: "Polygon", coordinates: [[...p.coords, p.coords[0]].map(([lat, lon]) => [lon, lat])] },
    })),
  });
}

export const SatelliteLayersView: React.FC<Props> = ({ selectedParcelId, onSelectParcel, onBackToChat }) => {
  const [manifest, setManifest] = useState<LayersManifest | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [layerId, setLayerId] = useState("ndvi");
  const [month, setMonth] = useState<string>("");
  const [month2, setMonth2] = useState<string>("");
  const [compare, setCompare] = useState(false);
  const [cmap, setCmap] = useState("RdYlGn");
  const [opacity, setOpacity] = useState(0.85);
  const [playing, setPlaying] = useState(false);
  const [base, setBase] = useState<keyof typeof BASES>("satellite");
  const [probe, setProbe] = useState<string>("Move the pointer over the map");
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const [clicked, setClicked] = useState<{ lat: number; lon: number } | null>(null);
  const pinRef = useRef<L.CircleMarker | null>(null);

  const mapDiv = useRef<HTMLDivElement>(null);
  const mapRef = useRef<L.Map | null>(null);
  const baseRef = useRef<L.TileLayer | null>(null);
  const overlayRef = useRef<L.ImageOverlay | null>(null);
  const polyRef = useRef<Record<string, L.Polygon>>({});
  const decodedRef = useRef<{ main: Decoded | null; kind: "gray" | "rgb" | "lulc" | "diff"; range: [number, number] | null; span?: number }>({ main: null, kind: "gray", range: null });

  useEffect(() => { fetchLayers().then(setManifest).catch((e) => setError(e.message)); }, []);

  const layer: LayerInfo | null = manifest?.layers[layerId] ?? null;
  const months = layer?.months ?? [];

  // when the layer changes: default palette and a valid month
  useEffect(() => {
    if (!layer) return;
    setCmap(DEFAULT_CMAP[layerId] || "Viridis");
    const ms = layer.months;
    setMonth((m) => (ms.includes(m) ? m : ms[ms.length - 1] || ""));
    setMonth2((m) => (ms.includes(m) ? m : ms[0] || ""));
    if (!GRAY.has(layerId) || ms[0] === "static") setCompare(false);
    setPlaying(false);
  }, [layerId, layer]);

  // map
  useEffect(() => {
    if (!manifest || !mapDiv.current || mapRef.current) return;
    const [[s, w], [n, e]] = manifest.bounds;
    const map = L.map(mapDiv.current, { zoomControl: true, attributionControl: true, maxZoom: 21 }).fitBounds([[s, w], [n, e]]);
    mapRef.current = map;
    makeZoomDraggable(map, "cropsy.drag.zoom.satellite");
    VILLAGE_PARCELS.forEach((p) => {
      const poly = L.polygon(p.coords, { color: "#ffffff", weight: 1, fillOpacity: 0, opacity: 0.55 }).addTo(map);
      poly.bindTooltip(`${p.id} · ${p.crop} (dummy label)`, { sticky: true });
      poly.on("click", () => onSelectParcel(p.id));
      polyRef.current[p.id] = poly;
    });
    map.on("click", (ev: L.LeafletMouseEvent) => setClicked({ lat: ev.latlng.lat, lon: ev.latlng.lng }));
    map.on("mousemove", (ev: L.LeafletMouseEvent) => {
      const d = decodedRef.current;
      const [[s2, w2], [n2, e2]] = manifest.bounds;
      const coord = `${ev.latlng.lat.toFixed(5)}, ${ev.latlng.lng.toFixed(5)}`;
      if (!d.main || ev.latlng.lat < s2 || ev.latlng.lat > n2 || ev.latlng.lng < w2 || ev.latlng.lng > e2) { setProbe(coord); return; }
      const x = Math.min(d.main.w - 1, Math.floor(((ev.latlng.lng - w2) / (e2 - w2)) * d.main.w));
      const y = Math.min(d.main.h - 1, Math.floor(((n2 - ev.latlng.lat) / (n2 - s2)) * d.main.h));
      const i = y * d.main.w + x;
      if (d.main.alpha[i] === 0) { setProbe(`${coord} · no data here`); return; }
      if (d.kind === "gray" && d.range) { const v = valueAt(d.main, i, d.range); setProbe(`${coord} · ${v == null ? "no data" : v.toFixed(3)}`); }
      else if (d.kind === "diff" && d.range && (d as any).second) setProbe(`${coord} · change ${((valueAt((d as any).second, i, d.range) ?? NaN) - (valueAt(d.main, i, d.range) ?? NaN)).toFixed(3)}`);
      else if (d.kind === "lulc") {
        const rgb = [d.main.rgba[i * 4], d.main.rgba[i * 4 + 1], d.main.rgba[i * 4 + 2]];
        const hit = Object.values(manifest.lulc_classes).find((c) => c.color.toLowerCase() === "#" + rgb.map((v) => v.toString(16).padStart(2, "0")).join(""));
        setProbe(`${coord} · ${hit?.name ?? "land cover"}`);
      } else setProbe(coord);
    });
    setTimeout(() => { map.invalidateSize(); map.fitBounds([[s, w], [n, e]]); }, 250);
    return () => { map.remove(); mapRef.current = null; };
  }, [manifest, onSelectParcel]);

  // base map
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    baseRef.current?.remove();
    baseRef.current = L.tileLayer(BASES[base].url, { attribution: BASES[base].attr, maxNativeZoom: 17, maxZoom: 21 }).addTo(map);
    baseRef.current.bringToBack();
  }, [base, manifest]);

  // highlight the selected parcel
  useEffect(() => {
    Object.entries(polyRef.current).forEach(([id, poly]) => poly.setStyle(id === selectedParcelId ? { color: "#f97316", weight: 3, opacity: 1 } : { color: "#ffffff", weight: 1, opacity: 0.55 }));
    polyRef.current[selectedParcelId]?.bringToFront();
  }, [selectedParcelId, manifest]);

  // draw the layer
  const draw = useCallback(async () => {
    if (!manifest || !layer || !mapRef.current || !month) return;
    if (!layer.months.includes(month)) return;      // the month for this layer is being reset: draw on the next pass
    setBusy(true);
    setNote(null);
    try {
      let canvas: HTMLCanvasElement;
      const range = layer.range;
      if (layerId === "lulc") { const d = await decode(layerUrl("lulc", "static")); canvas = plain(d); decodedRef.current = { main: d, kind: "lulc", range: null }; }
      else if (layerId === "tci" || layerId === "etci") { const d = await decode(layerUrl(layerId, month)); canvas = plain(d); decodedRef.current = { main: d, kind: "rgb", range: null }; }
      else if (layerId === "hybrid") {
        const [t, n] = await Promise.all([decode(layerUrl("tci", month)), decode(layerUrl("ndvi", month))]);
        canvas = blend(plain(t), colorize(n, "RdYlGn"), 0.5);
        decodedRef.current = { main: n, kind: "gray", range: manifest.layers.ndvi.range };
      } else if (layerId === "colorblind") {
        const n = await decode(layerUrl("ndvi", month)); canvas = colorize(n, "Cividis");
        decodedRef.current = { main: n, kind: "gray", range: manifest.layers.ndvi.range };
      } else if (compare && month2 && month2 !== month && range) {
        const [a, b] = await Promise.all([decode(layerUrl(layerId, month2 < month ? month2 : month)), decode(layerUrl(layerId, month2 < month ? month : month2))]);
        const span = (range[1] - range[0]) * 0.25;
        canvas = difference(a, b, range, span);
        decodedRef.current = { main: a, kind: "diff", range, span, ...({ second: b } as object) } as any;
      } else {
        const d = await decode(layerUrl(layerId, layer.months[0] === "static" ? "static" : month));
        canvas = colorize(d, cmap);
        decodedRef.current = { main: d, kind: "gray", range };
      }
      const [[s, w], [n, e]] = manifest.bounds;
      overlayRef.current?.remove();
      overlayRef.current = L.imageOverlay(toUrl(canvas), [[s, w], [n, e]], { opacity, interactive: false }).addTo(mapRef.current);
      Object.values(polyRef.current).forEach((p) => p.bringToFront());
    } catch (err: any) {
      setNote(err?.message || "Could not draw this layer");
    } finally {
      setBusy(false);
    }
  }, [manifest, layer, layerId, month, month2, compare, cmap, opacity]);

  useEffect(() => { draw(); }, [draw]);
  useEffect(() => { overlayRef.current?.setOpacity(opacity); }, [opacity]);

  // timelapse
  useEffect(() => {
    if (!playing || months.length < 2 || months[0] === "static") return;
    const t = setInterval(() => setMonth((m) => months[(months.indexOf(m) + 1) % months.length]), 1500);
    return () => clearInterval(t);
  }, [playing, months]);

  const grouped = useMemo(() => GROUPS.map((g) => ({ g, items: Object.values(manifest?.layers || {}).filter((l) => l.group === g) })).filter((x) => x.items.length), [manifest]);
  const isStatic = months[0] === "static";
  const lulcPresent = manifest ? Object.entries(manifest.stats?.lulc || {}).map(([name, frac]) => ({ name, frac: Number(frac) })) : [];

  return (
    <div className="w-full min-h-[calc(100vh-3.5rem)] bg-background text-foreground p-4 lg:p-6 flex flex-col gap-5">
      <PageHeader onBack={onBackToChat} crumb="Satellite layers & index results · Then Malai" right={<Badge tone="ok">Sentinel-1/2, WorldCover, SoilGrids, Copernicus DEM</Badge>} />
      <p className="text-[11.5px] text-muted-foreground/70">
        Sixteen map layers, almost all from real satellite and reference data at the parcels' true coordinates. The crop names, stages and issues of this demo village are dummy, so
        read the layers as "what the ground is really doing here". Modelled and own-definition layers are labelled.
      </p>

      {error && <Empty>{error}. Start the backend (port 8000), then run backend/scripts/build_layers.py.</Empty>}
      {!manifest && !error && <Empty>Loading layers…</Empty>}

      {manifest && (
        <div className="grid grid-cols-1 xl:grid-cols-[300px_1fr] gap-4">
          <div className="flex flex-col gap-3">
            <Card title="What do you want to know?">
              <div className="max-h-[52vh] overflow-y-auto pr-1">
                <LayerPicker layers={manifest.layers} value={layerId} onChange={setLayerId} />
              </div>
            </Card>

            <Card title="Map controls">
              {!isStatic && months.length > 0 && (
                <>
                  <label className="text-[11px] text-muted-foreground/70 flex flex-col gap-1">Month
                    <select value={month} onChange={(e) => setMonth(e.target.value)} className="bg-background border border-border rounded px-2 py-1 text-xs text-foreground">
                      {months.map((m) => <option key={m} value={m}>{monthLabel(m)}</option>)}
                    </select>
                  </label>
                  <button onClick={() => setPlaying((p) => !p)} className="rounded border border-border px-3 py-1 text-xs hover:border-success/60">{playing ? "Pause timelapse" : "Play season timelapse"}</button>
                </>
              )}
              {GRAY.has(layerId) && !isStatic && (
                <>
                  <label className="text-[11px] text-muted-foreground/70 flex flex-col gap-1">Colour palette
                    <select value={cmap} onChange={(e) => setCmap(e.target.value)} disabled={compare} className="bg-background border border-border rounded px-2 py-1 text-xs text-foreground disabled:opacity-40">
                      {COLORMAP_NAMES.map((c) => <option key={c} value={c}>{c}{c === "Cividis" ? " (colour-blind safe)" : ""}</option>)}
                    </select>
                  </label>
                  <label className="flex items-center gap-2 text-xs text-muted-foreground"><input type="checkbox" checked={compare} onChange={(e) => setCompare(e.target.checked)} /> Compare two months</label>
                  {compare && (
                    <label className="text-[11px] text-muted-foreground/70 flex flex-col gap-1">Compare {monthLabel(month)} with
                      <select value={month2} onChange={(e) => setMonth2(e.target.value)} className="bg-background border border-border rounded px-2 py-1 text-xs text-foreground">
                        {months.filter((m) => m !== month).map((m) => <option key={m} value={m}>{monthLabel(m)}</option>)}
                      </select>
                    </label>
                  )}
                </>
              )}
              {GRAY.has(layerId) && isStatic && (
                <label className="text-[11px] text-muted-foreground/70 flex flex-col gap-1">Colour palette
                  <select value={cmap} onChange={(e) => setCmap(e.target.value)} className="bg-background border border-border rounded px-2 py-1 text-xs text-foreground">
                    {COLORMAP_NAMES.map((c) => <option key={c} value={c}>{c}</option>)}
                  </select>
                </label>
              )}
              <label className="text-[11px] text-muted-foreground/70 flex flex-col gap-1">Layer opacity {Math.round(opacity * 100)}%
                <input type="range" min={0.1} max={1} step={0.05} value={opacity} onChange={(e) => setOpacity(Number(e.target.value))} />
              </label>
              <label className="text-[11px] text-muted-foreground/70 flex flex-col gap-1">Base map
                <select value={base} onChange={(e) => setBase(e.target.value as keyof typeof BASES)} className="bg-background border border-border rounded px-2 py-1 text-xs text-foreground">
                  <option value="satellite">Satellite</option><option value="street">Street</option><option value="dark">Dark</option>
                </select>
              </label>
              <div className="flex gap-2 pt-1">
                <button onClick={() => download("then_malai_parcels.kml", parcelsKml(), "application/vnd.google-earth.kml+xml")} className="flex-1 rounded border border-border px-2 py-1 text-[11px] hover:border-success/60">Export KML</button>
                <button onClick={() => download("then_malai_parcels.geojson", parcelsGeoJson(), "application/geo+json")} className="flex-1 rounded border border-border px-2 py-1 text-[11px] hover:border-success/60">Export GeoJSON</button>
              </div>
            </Card>
            <CoordinateLookup
              clicked={clicked}
              onFlyTo={(lat, lon) => {
                const map = mapRef.current;
                if (!map) return;
                map.flyTo([lat, lon], 17, { duration: 0.8 });
                pinRef.current?.remove();
                pinRef.current = L.circleMarker([lat, lon], { radius: 7, color: "#f97316", weight: 3, fillColor: "#ffffff", fillOpacity: 0.9 }).addTo(map);
              }}
            />
          </div>

          <div className="flex flex-col gap-3">
            <div className="relative rounded-xl overflow-hidden border border-border">
              <div ref={mapDiv} className="h-[540px] w-full" />
              <div className="absolute top-2 left-12 right-2 z-[1000] flex items-center justify-between pointer-events-none">
                <span className="pointer-events-auto rounded bg-black/70 px-2 py-1 font-mono text-[11px] text-foreground">
                  {layer?.name}{!isStatic && month ? ` · ${compare && month2 ? `${monthLabel(month2 < month ? month2 : month)} → ${monthLabel(month2 < month ? month : month2)}` : monthLabel(month)}` : ""}{busy ? " · drawing…" : ""}
                </span>
                <span className="rounded bg-black/70 px-2 py-1 font-mono text-[11px] text-muted-foreground">{probe}</span>
              </div>
              <div className="absolute bottom-6 left-2 z-[1000] rounded bg-black/75 px-3 py-2 w-64">
                {compare && GRAY.has(layerId) ? (
                  <>
                    <div className="h-2.5 rounded" style={{ background: gradientCss("RdBu") }} />
                    <div className="flex justify-between font-mono text-[10px] text-foreground pt-0.5"><span>fell</span><span>no change</span><span>rose</span></div>
                    <div className="text-[9.5px] text-muted-foreground">later month minus earlier month</div>
                  </>
                ) : layerId === "lulc" ? (
                  <div className="flex flex-col gap-0.5">
                    {lulcPresent.filter((c) => c.frac >= 0.005).map((c) => {
                      const def = Object.values(manifest.lulc_classes).find((k) => k.name === c.name);
                      return <div key={c.name} className="flex items-center gap-1.5 text-[10px] text-foreground"><span className="w-3 h-3 rounded-sm" style={{ background: def?.color }} />{c.name} {Math.round(c.frac * 100)}%</div>;
                    })}
                  </div>
                ) : layerId === "tci" || layerId === "etci" ? (
                  <div className="text-[10px] text-foreground">Natural colour. Clouds appear white.</div>
                ) : (
                  <>
                    <div className="h-2.5 rounded" style={{ background: gradientCss(layerId === "colorblind" ? "Cividis" : layerId === "hybrid" ? "RdYlGn" : cmap) }} />
                    <div className="flex justify-between font-mono text-[10px] text-foreground pt-0.5">
                      <span>{(manifest.layers[layerId === "colorblind" || layerId === "hybrid" ? "ndvi" : layerId]?.range?.[0] ?? 0).toFixed(1)}</span>
                      <span>{(layer?.units || "").length <= 16 ? layer?.units : ""}</span>
                      <span>{(manifest.layers[layerId === "colorblind" || layerId === "hybrid" ? "ndvi" : layerId]?.range?.[1] ?? 1).toFixed(1)}</span>
                    </div>
                  </>
                )}
              </div>
            </div>
            {note && <p className="text-xs text-warning">{note}</p>}

            {layer && (
              <Card title={layer.name} right={<Badge tone={KIND_TONE[layer.kind]}>{KIND_TEXT[layer.kind]}</Badge>}>
                <p className="text-xs text-foreground"><span className="text-muted-foreground/70">What it shows: </span>{layer.what}</p>
                <p className="text-xs text-foreground"><span className="text-muted-foreground/70">When to use it: </span>{layer.use}</p>
                <p className="text-xs text-warning"><span className="text-muted-foreground/70">Limits: </span>{layer.caveat}</p>
                <p className="font-mono text-[10.5px] text-muted-foreground/70">Source: {layer.source}</p>
              </Card>
            )}

            {Object.keys(manifest.sanity || {}).length > 0 && (
              <details className="rounded-xl border border-border bg-card p-3 text-xs text-muted-foreground">
                <summary className="cursor-pointer text-foreground">How the layers were checked</summary>
                <p className="pt-2">Each index was compared with the independent ESA WorldCover land-cover map. Median values over the year:</p>
                <table className="mt-1 w-full font-mono text-[11px]">
                  <thead><tr className="text-left text-muted-foreground/70"><th>Land cover</th><th>Pixels</th><th>NDVI</th><th>NDWI</th></tr></thead>
                  <tbody>{Object.entries(manifest.sanity).map(([k, v]: [string, any]) => <tr key={k}><td>{k}</td><td>{v.pixels}</td><td>{v.median_ndvi}</td><td>{v.median_ndwi}</td></tr>)}</tbody>
                </table>
                <p className="pt-1">Open water should have the highest NDWI and the lowest NDVI; tree cover and cropland should have the highest NDVI.</p>
              </details>
            )}
          </div>
        </div>
      )}

      {/* full width, the three downloads side by side */}
      <BulkExport />

      <div className="border-t border-border pt-4">
        <IndexResultsPanel parcelId={selectedParcelId} />
      </div>
    </div>
  );
};

export default SatelliteLayersView;
