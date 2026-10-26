import { getApiSettings, type FertilizerGuide } from "@/lib/cropsy-api";
import { PlannerCalc } from "./PlannerCalc";
import { StcrCalc } from "./StcrCalc";
import { clientLazy } from "./client-lazy";

const SpreadPanel = clientLazy(() => import("./SpreadPanel").then((m) => ({ default: m.SpreadPanel })), null);
const RegretPanel = clientLazy(() => import("./RegretPanel").then((m) => ({ default: m.RegretPanel })), null);
const OfficesMiniMap = clientLazy(() => import("./OfficesMiniMap").then((m) => ({ default: m.OfficesMiniMap })), null);

/** How to make or apply a fertilizer: photos, plain steps, the source, and tutorial-video searches. Fixed, reviewed content. */
export function FertilizerGuides({ guides, onAsk }: { guides: FertilizerGuide[]; onAsk?: (q: string) => void }) {
  const base = (getApiSettings().baseUrl || "").replace(/\/$/, "");
  return (
    <div className="mt-3 grid min-w-0 grid-cols-[minmax(0,1fr)] gap-3">
      {guides.map((g) => (
        <section key={g.id} className={`rounded-xl border p-3 ${g.kind === "emergency" ? "border-destructive/50 bg-destructive/5" : "border-border bg-card/60"}`}>
          <h4 className="mb-2 flex flex-wrap items-center gap-2 text-xs font-semibold">
            {g.title}
            <span className="rounded border border-border bg-muted px-1.5 py-0.5 font-mono text-[10px] font-normal uppercase text-muted-foreground">{g.kind === "natural" ? "home-made / natural" : g.kind === "protection" ? "land protection" : g.kind === "emergency" ? "emergency" : g.kind === "knowledge" ? "good to know" : g.kind === "weather" ? "weather" : g.kind === "calendar" ? "calendar" : g.kind === "gallery" ? "what it looks like" : g.kind === "clarify" ? "tell me more" : g.kind === "planner" ? "planner" : g.kind === "priority" ? "priority" : g.kind === "offices" ? "where to go" : g.kind === "reviewed" ? "officer reviewed" : g.kind === "spread" ? "village scan" : g.kind === "regret" ? "regret engine" : g.kind === "stcr" ? "soil-test dose" : "mineral"}</span>
          </h4>
          {g.photos.length > 0 && (
            <div className={`mb-2 grid gap-2 ${g.photos.length > 1 ? "sm:grid-cols-2" : ""}`}>
              {g.photos.map((p) => (
                <figure key={p.url} className="min-w-0">
                  <a href={`${base}${p.url}`} target="_blank" rel="noreferrer" title="Open the full-size photo">
                    <img src={`${base}${p.url}`} alt={p.caption || g.title} className="h-56 w-full rounded-lg border border-border object-cover sm:h-52" loading="lazy" />
                  </a>
                  <figcaption className="mt-1 text-[10.5px] leading-snug text-muted-foreground">
                    {p.caption && <span className="block text-foreground/80">{p.caption}</span>}
                    Photo: <a href={p.page} target="_blank" rel="noreferrer" className="text-primary hover:underline">{p.credit}</a>
                  </figcaption>
                </figure>
              ))}
            </div>
          )}
          {g.warning && <p className="mb-2 rounded-md border border-destructive/40 bg-destructive/10 p-2 text-[11px] font-medium text-destructive">⚠ {g.warning}</p>}
          {g.steps.length > 0 && <ol className={`space-y-1 pl-4 text-xs text-foreground/90 ${g.kind === "calendar" || g.kind === "gallery" || g.kind === "priority" ? "list-none pl-0" : "list-decimal"}`}>{g.steps.map((s) => <li key={s} className={s.includes("you are here") ? "font-semibold text-primary" : ""}>{s}</li>)}</ol>}
          {g.forecast && g.forecast.length > 0 && (
            <div className="mt-2 grid grid-cols-7 gap-1 text-center text-[10px]">
              {g.forecast.map((d) => (
                <div key={d.day} className="rounded-lg border border-border bg-muted/40 px-0.5 py-1.5">
                  <div className="font-medium text-muted-foreground">{d.day.split(" ")[0]}</div>
                  <div className="text-base leading-none">{d.rain >= 25 ? "⛈" : d.rain >= 10 ? "🌧" : d.rain >= 2 ? "🌦" : "☀"}{(d.wind ?? 0) >= 30 ? "💨" : ""}</div>
                  <div className="mt-0.5 font-mono">{d.rain} mm</div>
                  <div className="font-mono text-muted-foreground">{d.tmax}°</div>
                </div>
              ))}
            </div>
          )}
          {g.offices && (
            <div className="mt-2 grid gap-2">
              <OfficesMiniMap data={g.offices} />
              <div className="grid gap-1.5">
                {g.offices.items.map((o, i) => (
                  <a key={o.name} href={o.directions} target="_blank" rel="noreferrer" className="flex items-center justify-between gap-2 rounded-lg border border-border bg-muted/40 px-3 py-2 text-xs hover:bg-accent">
                    <span className="min-w-0"><b>{i + 1}. {o.name}</b><span className="block text-muted-foreground">{o.km} km straight line · pin {o.precision.split(":")[0]}</span></span>
                    <span className="shrink-0 rounded-full border border-primary/50 bg-primary/10 px-2.5 py-1 font-medium text-primary">Directions ↗</span>
                  </a>
                ))}
              </div>
            </div>
          )}
          {g.regret && <RegretPanel initial={g.regret} sources={g.spread_sources ?? []} />}
          {g.spread && <SpreadPanel initial={g.spread} sources={g.spread_sources ?? []} />}
          {g.planner && <PlannerCalc plan={g.planner} />}
          {g.stcr && <StcrCalc init={g.stcr} />}
          {g.map_zones && (
            <button type="button" onClick={() => window.dispatchEvent(new CustomEvent("cropsy-zones", { detail: g.map_zones }))} className="mt-2 rounded-full border border-primary/50 bg-primary/10 px-3 py-1.5 text-xs font-medium text-primary" data-testid="show-zones">Show these zones on the map</button>
          )}
          {g.asks && g.asks.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1.5">
              {g.asks.map((a) => (
                <button key={a.label} type="button" onClick={() => onAsk?.(a.query)} className="rounded-full border border-primary/50 bg-primary/10 px-3 py-1.5 text-xs font-medium text-primary hover:bg-primary/20">{a.label}</button>
              ))}
            </div>
          )}
          {g.notes && g.notes.length > 0 && <ul className="mt-2 list-disc space-y-0.5 pl-4 text-[11px] text-muted-foreground">{g.notes.map((n) => <li key={n}>{n}</li>)}</ul>}
          {g.contacts && g.contacts.length > 0 && (
            <div className="mt-2 rounded-lg border border-border bg-muted/50 p-2">
              <p className="mb-1 text-[11px] font-semibold">Who to call</p>
              <ul className="grid gap-1 text-[11px]">
                {g.contacts.map((c) => (
                  <li key={c.number} className="flex items-baseline justify-between gap-2">
                    <span className="text-muted-foreground">{c.name}</span>
                    <a href={`tel:${c.number.replace(/[^0-9]/g, "")}`} className="font-mono font-semibold text-primary hover:underline">{c.number}</a>
                  </li>
                ))}
              </ul>
              <p className="mt-1 text-[9.5px] text-muted-foreground">Numbers are the national and Tamil Nadu helplines at the time of writing; confirm locally.</p>
            </div>
          )}
          <p hidden={g.kind === "clarify"} className="mt-2 text-[10px] text-muted-foreground">
            Source: <a href={g.source.url} target="_blank" rel="noreferrer" className="text-primary hover:underline">{g.source.title}</a>
            {(g.extra_sources ?? []).map((x) => <span key={x.url}> · <a href={x.url} target="_blank" rel="noreferrer" className="text-primary hover:underline">{x.title}</a></span>)}
          </p>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {g.videos.map((v) => (
              <a key={v.url} href={v.url} target="_blank" rel="noreferrer" className="rounded-full border border-border bg-muted px-2.5 py-1 text-[10.5px] hover:bg-accent">▶ Find videos: {v.label}</a>
            ))}
          </div>
          <p hidden={g.videos.length === 0} className="mt-1 text-[9.5px] text-muted-foreground">These open a YouTube search; pick a video from a trusted source (TNAU, KVK) in your language.</p>
        </section>
      ))}
    </div>
  );
}
