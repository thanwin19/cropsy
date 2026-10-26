import { useEffect, useRef, useState } from "react";
import { fetchLayers, layerUrl, type LayersManifest } from "@/lib/cropsy-api";
import { VILLAGE_PARCELS } from "@/data/villageParcels.generated";
import { colorize, decode, plain } from "@/lib/rasterLayers";
import { gradientCss } from "@/lib/colormaps";
import { DEFAULT_PALETTE } from "@/lib/layerRender";

/** The four layers a farmer can read at a glance, each with a one-line meaning and which way is "better". */
const PICKS = [
  { id: "ndvi", title: "Crop greenness (NDVI)", low: "bare / stressed", high: "dense and green" },
  { id: "ndmi", title: "Moisture in the crop (NDMI)", low: "dry leaves", high: "water-rich leaves" },
  { id: "rsm", title: "Soil wetness, radar (RSM)", low: "dry soil", high: "wet soil" },
  { id: "tci", title: "True colour (what the satellite sees)", low: "", high: "" },
] as const;

const SIZE = 150;

function Thumb({ manifest, pick, parcelId, value }: { manifest: LayersManifest; pick: (typeof PICKS)[number]; parcelId: string; value?: string }) {
  const ref = useRef<HTMLCanvasElement>(null);
  const [state, setState] = useState<"loading" | "ok" | "none">("loading");
  const info = manifest.layers[pick.id];

  useEffect(() => {
    const parcel = VILLAGE_PARCELS.find((p) => p.id === parcelId);
    const months = info?.months ?? [];
    if (!parcel || !months.length) return setState("none");
    const month = months[months.length - 1];
    let live = true;
    decode(layerUrl(pick.id, month))
      .then((d) => {
        if (!live || !ref.current) return;
        const [[s, w], [n, e]] = manifest.bounds;
        const px = (lat: number, lon: number) => [((lon - w) / (e - w)) * d.w, ((n - lat) / (n - s)) * d.h] as const;
        const pts = parcel.coords.map(([lat, lon]) => px(lat, lon));
        const xs = pts.map((p) => p[0]), ys = pts.map((p) => p[1]);
        const cx = (Math.min(...xs) + Math.max(...xs)) / 2, cy = (Math.min(...ys) + Math.max(...ys)) / 2;
        const side = Math.max(Math.max(...xs) - Math.min(...xs), Math.max(...ys) - Math.min(...ys), 6) * 2.6;
        const src = pick.id === "tci" ? plain(d) : colorize(d, DEFAULT_PALETTE[pick.id] || "Viridis");
        const c = ref.current;
        c.width = c.height = SIZE;
        const ctx = c.getContext("2d")!;
        ctx.imageSmoothingEnabled = false;
        ctx.fillStyle = "#111";
        ctx.fillRect(0, 0, SIZE, SIZE);
        ctx.drawImage(src, cx - side / 2, cy - side / 2, side, side, 0, 0, SIZE, SIZE);
        const k = SIZE / side;
        ctx.beginPath();
        pts.forEach(([x, y], i) => {
          const X = (x - (cx - side / 2)) * k, Y = (y - (cy - side / 2)) * k;
          i ? ctx.lineTo(X, Y) : ctx.moveTo(X, Y);
        });
        ctx.closePath();
        ctx.lineWidth = 2;
        ctx.strokeStyle = "#ffffff";
        ctx.stroke();
        setState("ok");
      })
      .catch(() => live && setState("none"));
    return () => {
      live = false;
    };
  }, [manifest, pick.id, parcelId, info]);

  if (state === "none") return null;
  return (
    <figure className="w-[150px] shrink-0">
      <canvas ref={ref} width={SIZE} height={SIZE} className="size-[150px] rounded-lg border border-border bg-black/40" aria-label={`${pick.title} around ${parcelId}`} />
      <figcaption className="mt-1 text-[10.5px] leading-snug">
        <b className="block text-xs font-medium">{pick.title}</b>
        {value && <span className="font-mono text-foreground">{value}</span>}
        {pick.id !== "tci" && (
          <>
            <span className="mt-1 block h-1.5 rounded-full" style={{ background: gradientCss(DEFAULT_PALETTE[pick.id] || "Viridis") }} />
            <span className="flex justify-between text-[9.5px] text-muted-foreground"><span>{pick.low}</span><span>{pick.high}</span></span>
          </>
        )}
      </figcaption>
    </figure>
  );
}

/** Small pictures of the parcel on the satellite layers, outlined in white, so the numbers can be understood by eye. */
export function ParcelLayerThumbs({ parcelId, values }: { parcelId: string; values: Record<string, string> }) {
  const [manifest, setManifest] = useState<LayersManifest | null>(null);
  useEffect(() => {
    fetchLayers().then(setManifest).catch(() => undefined);
  }, []);
  if (!manifest) return null;
  return (
    <section className="rounded-xl border border-border bg-card/60 p-3">
      <h4 className="mb-2 text-xs font-semibold">How {parcelId} looks from space (white outline = this parcel)</h4>
      <div className="flex gap-3 overflow-x-auto pb-1">
        {PICKS.map((p) => (
          <Thumb key={p.id} manifest={manifest} pick={p} parcelId={parcelId} {...(values[p.id] ? { value: values[p.id] } : {})} />
        ))}
      </div>
      <p className="mt-1 text-[10px] text-muted-foreground">Real satellite data, latest month. Greener or bluer is not always better: compare with the parcel's own history and the village.</p>
    </section>
  );
}
