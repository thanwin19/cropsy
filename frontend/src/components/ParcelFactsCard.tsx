import { getApiSettings, type ParcelFacts, type WildlifeRisk } from "@/lib/cropsy-api";
import { clientLazy } from "./client-lazy";

const ParcelLayerThumbs = clientLazy(() => import("./ParcelLayerThumbs").then((m) => ({ default: m.ParcelLayerThumbs })), null);

const Tag = ({ children }: { children: React.ReactNode }) => (
  <span className="whitespace-nowrap rounded border border-border bg-muted px-1.5 py-0.5 font-mono text-[10px] uppercase text-muted-foreground">{children}</span>
);

const Row = ({ k, v, tag }: { k: string; v: React.ReactNode; tag?: string }) => (
  <div className="flex items-baseline justify-between gap-3 border-b border-border/60 py-1.5 text-xs last:border-0">
    <span className="text-muted-foreground">{k}</span>
    <span className="flex items-baseline gap-2 text-right font-mono text-foreground">
      {v}
      {tag && <Tag>{tag}</Tag>}
    </span>
  </div>
);

const LEVEL_TONE: Record<string, string> = {
  high: "border-destructive/40 bg-destructive/10 text-destructive",
  medium: "border-warning/40 bg-warning/10 text-warning",
  low: "border-border bg-muted text-muted-foreground",
  unlikely: "border-border bg-muted text-muted-foreground/60",
};

/** Which animals are likely at a parcel, why, how to protect the crop, and the published sources behind it. */
export function WildlifeSection({ w }: { w: WildlifeRisk }) {
  return (
    <section className="rounded-xl border border-border bg-card/60 p-3">
      <h4 className="mb-1 text-xs font-semibold">Wildlife risk · {w.zone} zone · {w.crop}</h4>
      <p className="mb-2 text-[10.5px] text-muted-foreground">{w.kind}</p>
      <div className="divide-y divide-border/60">
        {w.animals.map((a) => (
          <details key={a.animal} className="py-1.5 text-xs" open={a.level === "high"}>
            <summary className="flex cursor-pointer items-center justify-between gap-2">
              <span>{a.animal}</span>
              <span className={`rounded-full border px-2 py-0.5 font-mono text-[10px] ${LEVEL_TONE[a.level]}`}>{a.level}</span>
            </summary>
            <div className="mt-1.5 space-y-1 pl-1 text-[11px] text-muted-foreground">
              {a.photo && (
                <figure className="overflow-hidden rounded-lg border border-border bg-black/30">
                  <img src={`${(getApiSettings().baseUrl || "").replace(/\/$/, "")}${a.photo.url}`} alt={a.photo.caption} className="max-h-64 w-full object-cover" loading="lazy" />
                  <figcaption className="p-1.5 text-[10px] leading-snug">
                    {a.photo.caption}. Photo: <a href={a.photo.page} target="_blank" rel="noreferrer" className="text-primary hover:underline">{a.photo.credit}</a>
                  </figcaption>
                </figure>
              )}
              <p>{a.why}. Evidence: {a.evidence}.</p>
              {a.crop_note && <p>{a.crop_note}</p>}
              {a.vulnerable_when && <p><b className="font-medium">Most at risk: </b>{a.vulnerable_when}.</p>}
              <ul className="list-disc space-y-0.5 pl-4 text-foreground/90">{a.deterrents.map((d) => <li key={d}>{d}</li>)}</ul>
              <p className="text-[10px]">Sources: {a.sources.map((s, i) => <span key={s.url}>{i > 0 && " · "}<a href={s.url} target="_blank" rel="noreferrer" className="text-primary underline-offset-2 hover:underline">{s.title.split(":")[0].split("(")[0].trim()}</a></span>)}</p>
            </div>
          </details>
        ))}
      </div>
      {w.crop_standing && <p className="mt-2 text-[11px]"><b className="font-medium">{w.crop} standing: </b>{w.crop_standing}</p>}
      <p className="mt-2 text-[10px] leading-snug text-muted-foreground">{w.evidence_note} {w.note}</p>
    </section>
  );
}

/** The full parcel record shown under a factual answer: owner, area, crop, soil, terrain, the 16 satellite layers and the photo. */
export function ParcelFactsCard({ facts }: { facts: ParcelFacts }) {
  if (!facts.parcel_id) {
    // a general wildlife answer: no parcel record, just the sources behind it
    const wg = facts.wildlife_general;
    const gbase = (getApiSettings().baseUrl || "").replace(/\/$/, "");
    return wg?.sources?.length ? (
      <div className="mt-3 grid min-w-0 gap-3">
        {wg.animals && wg.animals.length > 0 && (
          <div className="grid gap-2 sm:grid-cols-2">
            {wg.animals.map((a) => (
              <figure key={a.animal} className="min-w-0 overflow-hidden rounded-xl border border-border bg-black/30">
                <a href={`${gbase}${a.photo.url}`} target="_blank" rel="noreferrer" title="Open the full-size photo">
                  <img src={`${gbase}${a.photo.url}`} alt={a.photo.caption} className="h-52 w-full object-cover" loading="lazy" />
                </a>
                <figcaption className="p-2 text-[10.5px] leading-snug text-muted-foreground">
                  <b className="block text-foreground/90">{a.animal}</b>
                  {a.photo.caption}. Photo: <a href={a.photo.page} target="_blank" rel="noreferrer" className="text-primary hover:underline">{a.photo.credit}</a>
                </figcaption>
              </figure>
            ))}
          </div>
        )}
        <p className="text-[11px] text-muted-foreground">
          Sources: {wg.sources.map((s, i) => <span key={s.url}>{i > 0 && " · "}<a href={s.url} target="_blank" rel="noreferrer" className="text-primary hover:underline">{s.title.split(":")[0].split("(")[0].trim()}</a></span>)}
        </p>
      </div>
    ) : null;
  }
  const base = (getApiSettings().baseUrl || "").replace(/\/$/, "");
  const p = facts.photo;
  const stage = String(facts.crop.stage ?? "").split(" - ")[0];
  return (
    <div className="mt-3 grid min-w-0 grid-cols-[minmax(0,1fr)] gap-3">
      {p?.url && (
        <figure className="overflow-hidden rounded-xl border border-border bg-black/30">
          <img src={`${base}${p.url}`} alt={p.label} className="max-h-72 w-full object-cover" loading="lazy" />
          <figcaption className="flex items-start gap-2 p-2 text-[11px] text-muted-foreground">
            <Tag>{p.kind === "parcel" ? "parcel photo" : "representative"}</Tag>
            <span>{p.label}</span>
          </figcaption>
        </figure>
      )}

      <section className="rounded-xl border border-border bg-card/60 p-3">
        <h4 className="mb-1 text-xs font-semibold">Parcel {facts.parcel_id}</h4>
        <Row
          k="Owner"
          v={
            <span className="flex items-center gap-2">
              {facts.owner.avatar && <img src={`${base}${facts.owner.avatar}`} alt="Dummy owner picture" className="size-9 rounded-full border border-border" loading="lazy" />}
              {facts.owner.name ?? "n/a"}
            </span>
          }
          tag="dummy"
        />
        <Row k="Patta no." v={facts.owner.patta_no ?? "n/a"} tag="dummy" />
        <Row k="Field name" v={facts.field_name ?? "n/a"} />
        <Row k="Area" v={facts.area_ha != null ? `${facts.area_ha} ha (${(facts.area_ha * 2.471).toFixed(2)} acres)` : "n/a"} />
        <Row k="Crop" v={`${facts.crop.name} (${facts.crop.variety}) · ${stage} · day ${facts.crop.days_after_planting}`} tag="dummy" />
        <Row k="Location" v={`${facts.location.lat}, ${facts.location.lon}`} tag="real" />
        <Row k="Elevation / zone" v={`${facts.location.elevation_m} m · ${facts.zone}`} tag="real" />
        <Row k="Slope" v={facts.terrain.slope ?? "n/a"} tag="real" />
        {facts.terrain.direct_sun_hours != null && <Row k="Direct sun" v={`${facts.terrain.direct_sun_hours} h/day`} tag="real" />}
        <Row k="Soil record" v={`${facts.soil.texture ?? "n/a"} · pH ${facts.soil.ph ?? "n/a"}`} tag="dummy" />
        <Row k="Irrigation" v={`${facts.management.irrigation_type ?? "n/a"} · last ${facts.management.days_since_last_irrigation ?? "?"} days ago`} tag="dummy" />
        {facts.recorded_issue && <Row k="Recorded issue" v={`${facts.recorded_issue.label} (${facts.recorded_issue.severity})`} tag="dummy" />}
      </section>

      {facts.layers.length > 0 && (
        <ParcelLayerThumbs
          parcelId={facts.parcel_id}
          values={Object.fromEntries(facts.layers.filter((l) => typeof l.value === "number").map((l) => [l.id, `${l.value} ${l.units}`.trim()]))}
        />
      )}

      {facts.wildlife && <WildlifeSection w={facts.wildlife} />}

      {facts.layers.length > 0 && (
        <section className="rounded-xl border border-border bg-card/60 p-3">
          <h4 className="mb-1 text-xs font-semibold">Satellite layers at this parcel</h4>
          {facts.layers.map((l) => (
            <Row key={l.id} k={`${l.name} · ${l.month}`} v={`${l.value}${l.units && !String(l.value).startsWith("no") ? ` ${l.units}` : ""}`} tag={l.kind === "modelled" ? "modelled" : "real"} />
          ))}
          {facts.layers_note && <p className="pt-2 text-[10px] text-muted-foreground">{facts.layers_note}</p>}
        </section>
      )}
    </div>
  );
}
