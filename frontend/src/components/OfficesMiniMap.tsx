import { useEffect, useRef } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

export type OfficesData = {
  origin: { name: string; lat: number; lon: number };
  items: { name: string; kind: string; lat: number; lon: number; km: number; directions: string; precision: string }[];
};

/** A small map for the chat: where you are (green) and the nearest KVK or labs (numbered). Positions are approximate. */
export function OfficesMiniMap({ data }: { data: OfficesData }) {
  const div = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!div.current) return;
    const map = L.map(div.current, { zoomControl: true, attributionControl: true, scrollWheelZoom: false });
    L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}", { maxNativeZoom: 17, maxZoom: 18, attribution: "Esri World Imagery" }).addTo(map);
    const pin = (bg: string, label: string) =>
      L.divIcon({ className: "", html: `<div style="display:grid;place-items:center;width:26px;height:26px;border-radius:999px;background:${bg};color:#fff;font:700 12px sans-serif;border:2px solid #fff;box-shadow:0 2px 6px rgba(0,0,0,.6)">${label}</div>`, iconSize: [26, 26], iconAnchor: [13, 13] });
    const pts: [number, number][] = [[data.origin.lat, data.origin.lon]];
    L.marker([data.origin.lat, data.origin.lon], { icon: pin("#16a34a", "★") }).bindTooltip(data.origin.name).addTo(map);
    data.items.forEach((o, i) => {
      pts.push([o.lat, o.lon]);
      L.polyline([[data.origin.lat, data.origin.lon], [o.lat, o.lon]], { color: "#f59e0b", weight: 2, dashArray: "5 6", opacity: 0.9 }).addTo(map);
      L.marker([o.lat, o.lon], { icon: pin(o.kind === "kvk" ? "#d97706" : "#2563eb", String(i + 1)) }).bindTooltip(`${i + 1}. ${o.name} (${o.km} km)`).addTo(map);
    });
    map.fitBounds(L.latLngBounds(pts).pad(0.25), { maxZoom: 12 });
    setTimeout(() => map.invalidateSize(), 150);
    return () => {
      map.remove();
    };
  }, [data]);
  return <div ref={div} className="h-56 w-full overflow-hidden rounded-lg border border-border" aria-label="Map of the nearest KVK and soil labs" />;
}
