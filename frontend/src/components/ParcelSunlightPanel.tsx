import { useMemo, useState } from "react";
import { useDraggable } from "../lib/useDraggable";
import { Sun, Download, ExternalLink, X } from "lucide-react";
import type { HorizonPoint } from "../lib/solarGeometry";
import {
  buildParcelsGeoJSON,
  sunlightForAllParcels,
  type ParcelLike,
} from "../lib/parcelSunlight";

interface Props {
  parcels: readonly ParcelLike[];
  horizonProfiles: Record<string, { profile?: HorizonPoint[] }>;
  date: Date;
  selId: string;
  onSelect: (id: string) => void;
  /** sit in the map's bottom tool row (not floating): the table opens upward from the button */
  docked?: boolean;
}

const SEASONS: Array<[string, number, number]> = [
  ["Mar 21", 2, 21],
  ["Jun 21", 5, 21],
  ["Sep 23", 8, 23],
  ["Dec 21", 11, 21],
];

/** Floating "Sunlight hours" table: terrain-aware direct sun per parcel + GIS export. */
export function ParcelSunlightPanel({ parcels, horizonProfiles, date, selId, onSelect, docked = false }: Props) {
  const d = useDraggable<HTMLDivElement>("cropsy.drag.sunlight");
  const [open, setOpen] = useState(false);
  const ready = Object.keys(horizonProfiles).length > 0;

  const today = useMemo(
    () => (open && ready ? sunlightForAllParcels(parcels, horizonProfiles, date) : []),
    [open, ready, parcels, horizonProfiles, date],
  );

  // Seasonal direct-sun hours for the selected parcel (4 dates in the date's year)
  const seasonal = useMemo(() => {
    if (!open || !ready) return [];
    const p = parcels.find((x) => x.id === selId);
    if (!p) return [];
    return SEASONS.map(([label, m, d]) => {
      const dt = new Date(Date.UTC(date.getUTCFullYear(), m, d));
      const r = sunlightForAllParcels([p], horizonProfiles, dt)[0];
      return { label, direct: r.directHours, loss: r.lossHours };
    });
  }, [open, ready, parcels, horizonProfiles, date, selId]);

  const dateLabel = date.toISOString().slice(0, 10);

  const download = () => {
    const gj = buildParcelsGeoJSON(parcels, today, dateLabel);
    const blob = new Blob([JSON.stringify(gj, null, 2)], { type: "application/geo+json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `then-malai-parcels-sunlight-${dateLabel}.geojson`;
    a.click();
    URL.revokeObjectURL(a.href);
  };

  return (
    <div {...(docked ? {} : { ref: d.ref, ...d.bind })} style={docked ? { position: "relative", zIndex: 13, pointerEvents: "auto" } : { position: "absolute", top: 52, left: "50%", translate: "-50% 0", zIndex: 13, pointerEvents: "auto", ...d.style }}>
      {!open ? (
        <button
          id="tm-sunlight-btn"
          onClick={() => setOpen(true)}
          aria-label="Sunlight hours"
          title="Sunlight hours"
          className="inline-flex h-9 w-9 items-center justify-center rounded-md border border-border bg-secondary text-secondary-foreground shadow-xl transition hover:bg-accent"
        >
          <Sun className="size-4 text-primary" />
        </button>
      ) : (
        <div
          style={{
            width: docked ? 480 : 360, maxWidth: "calc(100vw - 32px)", maxHeight: "min(68vh, 540px)", ...(docked ? { position: "absolute", bottom: "calc(100% + 10px)", right: 0, zIndex: 30 } : {}), overflow: "auto", padding: 18, borderRadius: 12,
            background: "color-mix(in oklab, var(--overlay) 95%, transparent)", border: "1px solid var(--border)",
            color: "#e7e5e4", font: "500 12px 'DM Mono',monospace", boxShadow: "0 8px 28px rgba(0,0,0,0.6)", lineHeight: 1.5,
          }}
        >
          <style>{`#tm-sunlight-table th{position:sticky;top:-18px;background:color-mix(in oklab, var(--overlay) 98%, transparent);padding:8px 10px;font-weight:600}#tm-sunlight-table td{padding:6px 10px;border-top:1px solid rgba(255,255,255,0.06)}`}</style>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12, fontSize: 13 }}>
            <b style={{ color: "var(--primary)" }}>Direct sun · {dateLabel}</b>
            <button onClick={() => setOpen(false)} aria-label="Close" style={{ background: "none", border: 0, color: "#a8a29e", cursor: "pointer" }}>
              <X size={14} />
            </button>
          </div>

          {!ready ? (
            <div style={{ color: "#a8a29e" }}>Loading horizon profiles…</div>
          ) : (
            <>
              <table id="tm-sunlight-table" style={{ width: "100%", borderCollapse: "collapse" }}>
                <thead>
                  <tr style={{ color: "#a8a29e", textAlign: "left" }}>
                    <th>Parcel</th><th>Crop</th><th>Sun h</th><th>Lost h</th><th>Window (IST)</th>
                  </tr>
                </thead>
                <tbody>
                  {today.map((r) => (
                    <tr
                      key={r.id}
                      onClick={() => onSelect(r.id)}
                      style={{ cursor: "pointer", background: r.id === selId ? "rgba(251,191,36,0.15)" : "transparent" }}
                    >
                      <td>{r.id}</td>
                      <td>{r.crop}</td>
                      <td style={{ color: "#fbbf24" }}>{r.directHours.toFixed(1)}</td>
                      <td style={{ color: r.lossHours > 1 ? "#38bdf8" : "#a8a29e" }}>{r.lossHours.toFixed(1)}</td>
                      <td>{r.firstSun}–{r.lastSun}</td>
                    </tr>
                  ))}
                </tbody>
              </table>

              <div style={{ marginTop: 18, color: "#a8a29e" }}>{selId} through the year (direct sun h / lost to terrain):</div>
              <div style={{ display: "flex", gap: 10, marginTop: 8 }}>
                {seasonal.map((s) => (
                  <div key={s.label} style={{ flex: 1, padding: 10, borderRadius: 8, background: "rgba(255,255,255,0.05)", textAlign: "center" }}>
                    <div style={{ color: "#a8a29e" }}>{s.label}</div>
                    <div style={{ color: "#fbbf24" }}>{s.direct.toFixed(1)}</div>
                    <div style={{ color: "#38bdf8" }}>-{s.loss.toFixed(1)}</div>
                  </div>
                ))}
              </div>

              <div style={{ display: "flex", gap: 10, marginTop: 18 }}>
                <button onClick={download} style={btn}><Download size={11} /> GeoJSON</button>
                <a href="https://web.geolibre.app/" target="_blank" rel="noreferrer" style={{ ...btn, textDecoration: "none" }}>
                  <ExternalLink size={11} /> Open GeoLibre
                </a>
              </div>
              <div style={{ marginTop: 4, color: "#78716c", fontSize: 9 }}>
                Download, then drag the .geojson into GeoLibre or QGIS to analyse parcels there.
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}

const btn: React.CSSProperties = {
  display: "flex", alignItems: "center", gap: 4, padding: "4px 8px", borderRadius: 6,
  border: "1px solid rgba(251,191,36,0.4)", background: "rgba(251,191,36,0.1)", color: "#fbbf24",
  font: "600 10px 'DM Mono',monospace", cursor: "pointer",
};
