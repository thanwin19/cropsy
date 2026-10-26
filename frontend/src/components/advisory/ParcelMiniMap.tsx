import React, { useEffect, useRef, useState } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { fetchLayers, layerUrl, type LayersManifest } from "@/lib/cropsy-api";
import { colorize, decode, plain, toUrl } from "@/lib/rasterLayers";
import { VILLAGE_PARCELS } from "../../data/villageParcels.generated";
import { makeZoomDraggable } from "../../lib/dragZoomControl";
import { Segmented } from "../stitch/ui";

let manifestPromise: Promise<LayersManifest> | null = null;
const manifest = () => (manifestPromise ??= fetchLayers().catch((e) => { manifestPromise = null; throw e; }));

type Mode = "ndvi" | "tci";

/** The selected parcel over the satellite picture, with the latest NDVI (or true colour) laid on top. */
export const ParcelMiniMap: React.FC<{ parcelId: string; lastVisit?: string | null }> = ({ parcelId, lastVisit }) => {
  const div = useRef<HTMLDivElement>(null);
  const mapRef = useRef<L.Map | null>(null);
  const overlay = useRef<L.ImageOverlay | null>(null);
  const outline = useRef<L.Polygon | null>(null);
  const [mode, setMode] = useState<Mode>("ndvi");
  const [month, setMonth] = useState<string>("");
  const [err, setErr] = useState<string | null>(null);
  const parcel = VILLAGE_PARCELS.find((p) => p.id === parcelId) || VILLAGE_PARCELS[0];

  useEffect(() => {
    if (!div.current || mapRef.current) return;
    const map = L.map(div.current, { zoomControl: false, attributionControl: false, scrollWheelZoom: false, maxZoom: 21 });
    L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}", { maxNativeZoom: 17, maxZoom: 21 }).addTo(map);
    L.control.zoom({ position: "topleft" }).addTo(map);
    mapRef.current = map;
    makeZoomDraggable(map, "cropsy.drag.zoom.mini");
    return () => { map.remove(); mapRef.current = null; };
  }, []);

  // outline + framing for the current parcel
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    outline.current?.remove();
    outline.current = L.polygon(parcel.coords, { color: "#ffffff", weight: 2.5, fillOpacity: 0 }).addTo(map);
    map.fitBounds(outline.current.getBounds(), { padding: [34, 34], maxZoom: 18 });
    setTimeout(() => map.invalidateSize(), 150);
  }, [parcel]);

  // the raster overlay (NDVI colours or true colour), latest month
  useEffect(() => {
    let live = true;
    (async () => {
      try {
        const m = await manifest();
        const months = m.layers[mode].months;
        const latest = months[months.length - 1];
        setMonth(latest);
        const d = await decode(layerUrl(mode, latest));
        const canvas = mode === "ndvi" ? colorize(d, "RdYlGn") : plain(d);
        if (!live || !mapRef.current) return;
        overlay.current?.remove();
        const [[s, w], [n, e]] = m.bounds;
        overlay.current = L.imageOverlay(toUrl(canvas), [[s, w], [n, e]], { opacity: mode === "ndvi" ? 0.82 : 1, interactive: false }).addTo(mapRef.current);
        outline.current?.bringToFront();
        setErr(null);
      } catch (e: any) {
        if (live) setErr(e?.message || "Satellite layer unavailable");
      }
    })();
    return () => { live = false; };
  }, [mode]);

  return (
    <div className="relative overflow-hidden rounded-2xl border border-white/[0.07] shadow-[0_10px_30px_-14px_rgba(0,0,0,0.7)]">
      <div ref={div} className="h-[300px] w-full bg-background" />
      <div className="absolute left-3 top-3 z-[1000]">
        <Segmented<Mode> value={mode} onChange={setMode} options={[{ value: "ndvi", label: "Crop health" }, { value: "tci", label: "True colour" }]} />
      </div>
      <div className="absolute inset-x-0 bottom-0 z-[1000] flex flex-wrap items-end justify-between gap-2 bg-gradient-to-t from-black/80 to-transparent px-3.5 pb-2.5 pt-8">
        <div>
          <div className="font-serif text-sm font-semibold text-white">{parcel.id} · {parcel.name}</div>
          <div className="font-mono text-[10.5px] text-white/70">{parcel.areaHa} ha · {parcel.crop} (dummy label)</div>
        </div>
        <div className="text-right font-mono text-[10.5px] text-white/70">
          <div>Last clear satellite view</div>
          <div className="text-white">{lastVisit || "none in the last year"}</div>
          {month && <div>map: {month}</div>}
        </div>
      </div>
      {err && <div className="absolute inset-x-3 top-14 z-[1000] rounded bg-black/70 px-2 py-1 text-[11px] text-warning">{err}</div>}
    </div>
  );
};

export default ParcelMiniMap;
