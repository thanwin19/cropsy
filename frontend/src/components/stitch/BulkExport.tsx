import React from "react";
import { getApiSettings } from "@/lib/cropsy-api";
import { Card, SourceNote } from "./ui";

const FILES = [
  {
    path: "/api/indices-export.csv",
    name: "All indices, all parcels (joined)",
    about: "One row per parcel and date with every optical and radar index side by side. Best for spreadsheets and charts.",
    cols: "parcel, date, then the optical indices (NDVI, EVI, SAVI, NDRE, NDMI, NDWI) and the radar indices (RVI, RSM)",
  },
  {
    path: "/api/export/ndvi_observations.csv",
    name: "Optical observations (Sentinel-2)",
    about: "Every clear Sentinel-2 pass for every parcel over the last two years, with quality columns.",
    cols: "parcel_id, date, ndvi/evi/savi/ndre/ndmi/ndwi means, NDVI by 8 compass sectors, ndvi_std, valid_frac, n_pixels, scene_id, scene_cloud_pct",
  },
  {
    path: "/api/export/radar_observations.csv",
    name: "Radar observations (Sentinel-1)",
    about: "Every Sentinel-1 pass for every parcel. Radar sees through cloud, so it fills the monsoon gaps in the optical record.",
    cols: "parcel_id, date, orbit, rvi_mean, rsm_mean (relative 0 to 1), vv_db, vh_db",
  },
] as const;

/** Bulk historical data: download the full satellite record behind every chart, as CSV. */
export const BulkExport: React.FC = () => {
  const base = (getApiSettings().baseUrl || "").replace(/\/$/, "");
  return (
    <Card title="Bulk historical data" eyebrow="Download everything">
      <div className="grid gap-3 md:grid-cols-3">
        {FILES.map((f) => (
          <div key={f.path} className="flex flex-col gap-2 rounded-xl border border-border bg-black/15 p-3">
            <div className="flex items-start justify-between gap-3">
              <span className="text-xs font-semibold text-foreground">{f.name}</span>
              <a
                href={`${base}${f.path}`}
                download
                className="shrink-0 rounded-lg border border-white/10 px-2.5 py-1 font-mono text-[11px] text-primary hover:border-primary/60"
              >
                Download CSV
              </a>
            </div>
            <p className="text-[11.5px] text-muted-foreground">{f.about}</p>
            <p className="font-mono text-[10px] leading-relaxed text-muted-foreground/70">Columns: {f.cols}</p>
          </div>
        ))}
      </div>
      <SourceNote>
        Real Sentinel-1 and Sentinel-2 values at the parcels' coordinates. Parcel crop names, stages and issues are dummy data and are not part of these files.
      </SourceNote>
    </Card>
  );
};

export default BulkExport;
