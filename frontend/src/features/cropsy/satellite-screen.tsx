import { useNavigate } from "@tanstack/react-router";
import { clientLazy } from "@/components/client-lazy";
import { SectionStrip } from "./ui";
import { useCropsy } from "./store";

// Leaflet needs the browser, so the explorer is loaded on the client only
const SatelliteLayersView = clientLazy(
  () => import("@/components/stitch/SatelliteLayersView").then((m) => ({ default: m.SatelliteLayersView })),
  <div className="grid min-h-[60vh] place-items-center text-xs text-muted-foreground">Loading the 16-layer explorer…</div>,
);

/**
 * Satellite: the 16 layers grouped by the question each one answers (real Sentinel-2 and Sentinel-1 data, with modelled and dummy
 * layers labelled), month and colormap, opacity, two-date comparison, timelapse, bulk historical CSV, KML export, coordinate lookup,
 * plant-count estimate, and the Index Results charts (date window, two indices compared, two seasons, CSV export).
 */
export function SatelliteScreen() {
  const c = useCropsy();
  const navigate = useNavigate();
  return (
    <div className="min-h-screen">
      <SectionStrip>
        <span className="text-sm font-medium">16-layer explorer</span>
        <span className="ml-2 hidden font-mono text-[10px] text-muted-foreground sm:inline">Then Malai · real Sentinel-2 / Sentinel-1 data</span>
      </SectionStrip>
      <SatelliteLayersView selectedParcelId={c.parcelOrDefault} onSelectParcel={c.selectParcel} onBackToChat={() => void navigate({ to: "/" })} />
    </div>
  );
}
