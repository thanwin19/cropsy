import { clientLazy } from "@/components/client-lazy";
import { cn } from "@/lib/utils";

/**
 * The parcel map. Everything the screens know about the map goes through this one component, so the engine behind it can change
 * without touching screen logic. The engine is the real Leaflet map of Then Malai (satellite, dark and street styles, the 120 parcel
 * polygons, the solar ephemeris, terrain shadow, cloud forecast, sunlight hours, the 16-layer quick view and the time scrubber).
 *
 * Leaflet needs the browser, so it is loaded on the client only and never in the server render.
 */
function MapSkeleton() {
  return (
    <div className="absolute inset-0 grid place-items-center bg-map">
      <div className="flex flex-col items-center gap-3 text-muted-foreground">
        <div className="size-8 animate-spin rounded-full border-2 border-border border-t-primary" />
        <p className="font-mono text-[11px]">Loading the Then Malai map…</p>
      </div>
    </div>
  );
}

const ThenMalaiMapView = clientLazy(() => import("@/components/ThenMalaiMapView").then((m) => ({ default: m.ThenMalaiMapView })), <MapSkeleton />);

export function FieldMap({
  selected,
  onSelect,
  compact = false,
}: {
  selected?: string | undefined;
  onSelect?: (id: string) => void;
  compact?: boolean;
}) {
  return (
    <div className={cn("field-map relative isolate h-full w-full overflow-hidden bg-map", compact ? "min-h-[540px]" : "min-h-[620px]")}>
      <ThenMalaiMapView dark initialParcelId={selected ?? "TM-01"} onParcelChange={(id) => onSelect?.(id)} />
    </div>
  );
}
