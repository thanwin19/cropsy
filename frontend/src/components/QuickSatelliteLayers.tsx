import { useCallback, useEffect, useRef, useState } from "react";
import L from "leaflet";
import { Layers, Satellite, X } from "lucide-react";
import { fetchLayers, type LayersManifest } from "../lib/cropsy-api";
import { COLORMAP_NAMES, gradientCss } from "../lib/colormaps";
import { DEFAULT_PALETTE, GREY_LAYERS, renderLayer } from "../lib/layerRender";
import { toUrl } from "../lib/rasterLayers";
import { useDraggable } from "../lib/useDraggable";
import { LayerPicker } from "./stitch/LayerPicker";

const GLASS = "color-mix(in oklab, var(--overlay) 96%, transparent)";
const BDR = "var(--border)";
const ACC = "var(--primary)";
const monthLabel = (m: string) => (m === "static" ? "single map" : new Date(m + "-15").toLocaleDateString("en-GB", { month: "short", year: "numeric" }));

/**
 * Front-of-map shortcut to all 16 satellite layers. A draggable icon chip (with the layer count) opens a panel with the
 * "What do you want to know?" picker, month, palette and opacity, and draws the chosen layer straight onto the main map.
 * The image sits in its own pane BELOW the parcel outlines, so parcels stay clickable.
 */
export function QuickSatelliteLayers({ getMap, docked = false }: { getMap: () => L.Map | null; docked?: boolean }) {
  const [open, setOpen] = useState(false);
  const [manifest, setManifest] = useState<LayersManifest | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [layerId, setLayerId] = useState<string | null>(null);
  const [month, setMonth] = useState("");
  const [cmap, setCmap] = useState("RdYlGn");
  const [opacity, setOpacity] = useState(0.8);
  const [busy, setBusy] = useState(false);
  const overlay = useRef<L.ImageOverlay | null>(null);
  const getMapRef = useRef(getMap);
  getMapRef.current = getMap;           // an inline getMap would otherwise restart the draw effect on every render
  const d = useDraggable<HTMLDivElement>("cropsy.drag.quicklayers");

  // load the manifest the first time the panel opens
  useEffect(() => {
    if (!open || manifest) return;
    fetchLayers().then(setManifest).catch((e) => setError(e?.message || "Could not load the layers"));
  }, [open, manifest]);

  const info = manifest && layerId ? manifest.layers[layerId] : null;
  const months = info?.months ?? [];

  const choose = (id: string) => {
    if (!manifest) return;
    const l = manifest.layers[id];
    setLayerId(id);
    setCmap(DEFAULT_PALETTE[id] || "Viridis");
    setMonth((m) => (l.months.includes(m) ? m : l.months[l.months.length - 1] || ""));
  };

  const clear = useCallback(() => {
    overlay.current?.remove();
    overlay.current = null;
    setLayerId(null);
  }, []);

  // draw / redraw
  useEffect(() => {
    const map = getMapRef.current();
    if (!map || !manifest || !layerId || !month || !manifest.layers[layerId].months.includes(month)) return;
    let live = true;
    setBusy(true);
    setError(null);
    renderLayer(manifest, layerId, month, cmap)
      .then((canvas) => {
        if (!live) return;
        if (!map.getPane("satellitePane")) {
          const p = map.createPane("satellitePane");
          p.style.zIndex = "350";                    // above the base tiles (200), below parcel outlines (400)
          p.style.pointerEvents = "none";
        }
        const [[s, w], [n, e]] = manifest.bounds;
        overlay.current?.remove();
        overlay.current = L.imageOverlay(toUrl(canvas), [[s, w], [n, e]], { pane: "satellitePane", opacity, interactive: false }).addTo(map);
      })
      .catch((e) => live && setError(e?.message || "Could not draw this layer"))
      .finally(() => live && setBusy(false));
    return () => { live = false; };
    // opacity is applied separately below so dragging the slider does not redraw
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [manifest, layerId, month, cmap]);

  useEffect(() => { overlay.current?.setOpacity(opacity); }, [opacity]);
  useEffect(() => () => { overlay.current?.remove(); }, []);

  const sel = { background: "rgba(255,255,255,0.06)", border: "1px solid rgba(255,255,255,0.12)", color: "var(--foreground)", borderRadius: 6, padding: "3px 6px", fontSize: 11 } as const;

  return (
    <div {...(docked ? {} : { ref: d.ref, ...d.bind })} className={docked ? "" : "bottom-[96px] sm:bottom-3"} style={docked ? { position: "relative", zIndex: 40, pointerEvents: "auto" } : { position: "absolute", left: 10, zIndex: 40, pointerEvents: "auto", ...d.style }}>
      {!open ? (
        <button
          type="button"
          onClick={() => setOpen(true)}
          title="View the 16 satellite layers on this map"
          aria-label="Open the 16 satellite layers"
          className="inline-flex h-9 items-center gap-2 rounded-md border border-border bg-secondary px-3 text-sm font-medium text-secondary-foreground shadow-xl transition hover:bg-accent"
        >
          <Layers className="size-4" />
          <span>16 layers{layerId && manifest ? ` · ${manifest.layers[layerId].name}` : ""}</span>
        </button>
      ) : (
        <div style={{ width: 300, maxHeight: "min(62vh, 520px)", display: "flex", flexDirection: "column", borderRadius: 12, background: GLASS,
                      border: `1px solid ${BDR}`, color: "var(--foreground)", boxShadow: "0 10px 30px rgba(0,0,0,0.65)" }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "8px 10px", borderBottom: "1px solid rgba(255,255,255,0.08)" }}>
            <span style={{ display: "flex", alignItems: "center", gap: 6, font: "700 11px 'DM Mono',monospace", color: ACC }}>
              <Satellite size={13} /> Satellite layers
            </span>
            <button type="button" aria-label="Close" onClick={() => setOpen(false)} style={{ background: "none", border: 0, color: "#a8a29e", cursor: "pointer" }}><X size={14} /></button>
          </div>

          <div data-nodrag style={{ overflowY: "auto", padding: 10, display: "flex", flexDirection: "column", gap: 10 }}>
            {!manifest && !error && <p style={{ fontSize: 11, color: "var(--muted-foreground)" }}>Loading layers…</p>}
            {error && <p style={{ fontSize: 11, color: "var(--destructive)" }}>{error}. Start the backend (port 8000).</p>}
            {manifest && <LayerPicker layers={manifest.layers} value={layerId ?? ""} onChange={choose} />}
          </div>

          {manifest && layerId && info && (
            <div data-nodrag style={{ padding: 10, borderTop: "1px solid rgba(255,255,255,0.08)", display: "flex", flexDirection: "column", gap: 7 }}>
              {months[0] !== "static" && months.length > 0 && (
                <label style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: 11, color: "var(--muted-foreground)" }}>Month
                  <select value={month} onChange={(e) => setMonth(e.target.value)} style={sel}>
                    {months.map((m) => <option key={m} value={m}>{monthLabel(m)}</option>)}
                  </select>
                </label>
              )}
              {GREY_LAYERS.has(layerId) && (
                <label style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: 11, color: "var(--muted-foreground)" }}>Palette
                  <select value={cmap} onChange={(e) => setCmap(e.target.value)} style={sel}>
                    {COLORMAP_NAMES.map((c) => <option key={c} value={c}>{c}{c === "Cividis" ? " (colour-blind safe)" : ""}</option>)}
                  </select>
                </label>
              )}
              <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 11, color: "var(--muted-foreground)" }}>Opacity
                <input type="range" min={0.1} max={1} step={0.05} value={opacity} onChange={(e) => setOpacity(Number(e.target.value))} style={{ flex: 1 }} />
                <span style={{ width: 28, textAlign: "right" }}>{Math.round(opacity * 100)}%</span>
              </label>
              {GREY_LAYERS.has(layerId) && info.range && (
                <div>
                  <div style={{ height: 8, borderRadius: 4, background: gradientCss(cmap) }} />
                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: 10, color: "var(--foreground)", fontFamily: "monospace" }}>
                    <span>{info.range[0]}</span><span>{info.units}</span><span>{info.range[1]}</span>
                  </div>
                </div>
              )}
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                <span style={{ fontSize: 10, color: "color-mix(in oklab, var(--muted-foreground) 70%, transparent)" }}>{busy ? "Drawing…" : "Real satellite data; crop labels are dummy"}</span>
                <button type="button" onClick={clear} style={{ ...sel, cursor: "pointer" }}>Remove layer</button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default QuickSatelliteLayers;
