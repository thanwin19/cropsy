import React from "react";
import type { Phase7AdvisoryResult } from "@/lib/cropsy-api";
import { THEN_MALAI_PARCELS } from "@/lib/parcels";
import { Badge, Card, DummyBadge, Empty, Kv, PageHeader } from "./ui";

interface EvidenceSourcesViewProps {
  selectedParcelId: string;
  onBackToChat: () => void;
  /** The most recent advisory response; sources, checks and "why this matters" come from it. */
  lastResult?: Phase7AdvisoryResult | null;
}

/** What the answer was based on: the parcel record (real vs dummy fields labelled), cited sources and verification. */
export const EvidenceSourcesView: React.FC<EvidenceSourcesViewProps> = ({ selectedParcelId, onBackToChat, lastResult }) => {
  const p = THEN_MALAI_PARCELS.find((x) => x.id === selectedParcelId) || THEN_MALAI_PARCELS[0];
  const obs: any = lastResult?.observability || {};
  const trace: any[] = obs.trace || [];
  const weather = trace.find((t) => t.step === "tools/weather");
  const sources = lastResult?.sources || [];
  const why: any[] = (lastResult as any)?.why_this_matters || [];
  const checks = lastResult?.verification?.checks || [];

  return (
    <div className="w-full min-h-[calc(100vh-3.5rem)] bg-background text-foreground p-4 lg:p-6 flex flex-col gap-5">
      <PageHeader onBack={onBackToChat} crumb={`Evidence & sources · ${p.id} · ${p.crop}`} />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card title="Parcel record used" right={<DummyBadge />}>
          <Kv k="Parcel" v={`${p.id} · ${p.name}`} />
          <Kv k="Crop / variety" v={`${p.crop} · ${p.variety}`} />
          <Kv k="Stage (from planting date)" v={`${p.stage.split(" - ")[0]} · ${p.daysAfterPlanting} days`} />
          <Kv k="Area · owner · patta" v={`${p.areaHa} ha · ${p.owner} · ${p.pattaNo}`} />
          <Kv k="Recorded issue" v={p.issueCode === "healthy" ? "None" : `${p.issue} (${p.severity})`} />
          <Kv k="Irrigation / fertilizer" v={`${p.irrigationDaysAgo} d / ${p.fertilizerDaysAgo} d ago`} />
          <div className="flex flex-wrap gap-2 pt-1">
            <Badge tone="dummy">owner, crop, issue, inputs: dummy</Badge>
            {p.anchor ? <Badge tone="real">coordinates, soil, terrain: real</Badge> : <Badge tone="dummy">generated parcel (elevation real, DEM)</Badge>}
          </div>
        </Card>

        <Card title="Location & terrain">
          <Kv k="Latitude, longitude" v={`${p.lat.toFixed(4)}, ${p.lon.toFixed(4)}`} />
          <Kv k="Elevation" v={`${p.elevM} m (Copernicus DEM 30 m)`} />
          <Kv k="Zone" v={p.zone} />
          <Kv k="Soil" v={`${p.soilTexture} · pH ${p.soilPh}`} />
          <Kv k="Drainage" v={p.drainageRisk.replace(/_/g, " ")} />
          <Kv k="Western ridge" v={`~${p.ridgeKm} km, ~${p.ridgeM} m${p.anchor ? "" : " (approximate)"}`} />
        </Card>
      </div>

      {!lastResult ? (
        <Empty>Ask a question in the chat. This page then lists the sources, weather and checks behind that answer.</Empty>
      ) : (
        <>
          <Card title="Weather used">
            {weather ? (
              <>
                <Kv
                  k="Source"
                  v={
                    <Badge tone={/cached/i.test(weather.output_summary) ? "warn" : "ok"}>
                      {/cached/i.test(weather.output_summary) ? "cached fallback" : "live (Open-Meteo)"}
                    </Badge>
                  }
                />
                <p className="text-xs text-muted-foreground">{weather.output_summary}</p>
              </>
            ) : (
              <p className="text-xs text-muted-foreground">This answer did not use weather data.</p>
            )}
          </Card>

          <Card title={`Cited sources (${sources.length})`}>
            {sources.length === 0 && <p className="text-xs text-muted-foreground">No document was cited for this answer.</p>}
            {sources.map((s, i) => (
              <div key={i} className="flex items-center justify-between gap-3 text-xs border-b border-border/50 py-1.5">
                <span className="text-foreground">
                  {s.title}
                  {s.page ? <span className="text-muted-foreground/70"> · page {s.page}</span> : null}
                </span>
                <Badge tone="ok">{s.provenance || "authoritative"}</Badge>
              </div>
            ))}
          </Card>

          {why.length > 0 && (
            <Card title="Why this matters">
              {why.map((w, i) => (
                <div key={i} className="text-xs border-b border-border/50 py-1.5">
                  <div className="text-foreground">{w.parcel_fact}</div>
                  <div className="text-muted-foreground">{w.mechanism}</div>
                  {w.source && <div className="text-muted-foreground/70 font-mono text-[11px]">{w.source}</div>}
                </div>
              ))}
            </Card>
          )}

          <Card title="Checks on this answer">
            {checks.map((c: any) => (
              <div key={c.check} className="flex items-center justify-between text-xs border-b border-border/50 py-1">
                <span className="font-mono text-muted-foreground">{c.check}</span>
                <Badge tone={c.passed ? "ok" : "warn"}>{c.passed ? "passed" : "flagged"}</Badge>
              </div>
            ))}
            {(lastResult.limitations || []).map((l, i) => (
              <p key={i} className="text-[11.5px] text-warning">
                {l}
              </p>
            ))}
          </Card>
        </>
      )}
    </div>
  );
};

export default EvidenceSourcesView;
