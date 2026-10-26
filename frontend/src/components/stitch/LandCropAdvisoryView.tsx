import React from "react";
import type { Phase7AdvisoryResult } from "@/lib/cropsy-api";
import { THEN_MALAI_PARCELS } from "@/lib/parcels";
import { Badge, Card, DummyBadge, Empty, Kv, PageHeader } from "./ui";

interface LandCropAdvisoryViewProps {
  selectedParcelId: string;
  onBackToChat: () => void;
  onAskQuestion?: (q: string) => void;
  /** The most recent advisory response, shown here when it is about this parcel. */
  lastResult?: Phase7AdvisoryResult | null;
}

const HORIZONS: { key: "immediate" | "next_24_hours" | "next_3_to_7_days" | "watch_for"; label: string }[] = [
  { key: "immediate", label: "Right now" },
  { key: "next_24_hours", label: "Next 24 hours" },
  { key: "next_3_to_7_days", label: "Next 3 to 7 days" },
  { key: "watch_for", label: "Watch for" },
];

/** Field advisory for the selected parcel: its record, quick questions, and the latest advisory for it. */
export const LandCropAdvisoryView: React.FC<LandCropAdvisoryViewProps> = ({ selectedParcelId, onBackToChat, onAskQuestion, lastResult }) => {
  const p = THEN_MALAI_PARCELS.find((x) => x.id === selectedParcelId) || THEN_MALAI_PARCELS[0];
  const stage = p.stage.split(" - ")[0];
  const relevant = lastResult && (lastResult.parcel_id === p.id || !lastResult.parcel_id) ? lastResult : null;

  const questions = [
    ...(p.issueCode !== "healthy"
      ? [{ label: `${p.issue}: how serious?`, q: `${p.id} shows ${p.issue}. How serious is it and what should I do?` }]
      : []),
    { label: "Rain this week: spray or fertilize?", q: `Will it rain at ${p.id} this week? Should I spray or fertilize now?` },
    { label: `Fertilizer plan for ${stage}`, q: `What fertilizer does ${p.id} need at the ${stage} stage?` },
    { label: "Irrigate today?", q: `Does ${p.id} need irrigation today?` },
    { label: "Calculate fertilizer for the whole parcel", q: `Calculate the urea, DAP and MOP quantity for ${p.id}.` },
  ];

  return (
    <div className="w-full min-h-[calc(100vh-3.5rem)] bg-background text-foreground p-4 lg:p-6 flex flex-col gap-5">
      <PageHeader onBack={onBackToChat} crumb={`Field advisory · ${p.id} · ${p.crop}`} right={<DummyBadge />} />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <Card title="Parcel summary" className="lg:col-span-1">
          <Kv k="Crop" v={`${p.crop} (${p.variety})`} />
          <Kv k="Stage" v={`${stage} · ${p.daysAfterPlanting} days`} />
          <Kv k="Planted" v={p.plantingDate} />
          <Kv k="Area" v={`${p.areaHa} ha`} />
          <Kv k="Soil" v={`${p.soilTexture} · pH ${p.soilPh}`} />
          <Kv k="Zone · elevation" v={`${p.zone} · ${p.elevM} m`} />
          <Kv k="Drainage" v={p.drainageRisk.replace(/_/g, " ")} />
          <Kv k="Recorded issue" v={p.issueCode === "healthy" ? "None" : `${p.issue} (${p.severity})`} />
          <Kv k="Last irrigation" v={`${p.irrigationDaysAgo} days ago`} />
          <Kv k="Last fertilizer" v={`${p.fertilizerDaysAgo} days ago`} />
        </Card>

        <Card title="Ask about this parcel" className="lg:col-span-2">
          <div className="flex flex-wrap gap-2">
            {questions.map((x) => (
              <button
                key={x.label}
                onClick={() => onAskQuestion?.(x.q)}
                className="rounded-full border border-border bg-card px-3 py-1.5 text-xs text-foreground hover:border-success/60 hover:text-success transition-colors"
              >
                {x.label}
              </button>
            ))}
          </div>
          <p className="text-[11px] text-muted-foreground/70">
            Each question runs the full pipeline on this parcel. The answer appears in the chat and below.
          </p>
        </Card>
      </div>

      {!relevant ? (
        <Empty>No advisory for {p.id} yet. Pick a question above or ask in the chat.</Empty>
      ) : (
        <>
          <Card
            title="Latest advisory"
            right={
              <div className="flex gap-2">
                <Badge tone="ok">{relevant.route}</Badge>
                <Badge tone={relevant.verification?.status === "pass" ? "ok" : "warn"}>{relevant.verification?.status || "n/a"}</Badge>
              </div>
            }
          >
            <p className="text-sm text-foreground leading-relaxed select-text">{relevant.answer}</p>
            {(relevant.recommendations || []).length > 0 && (
              <ul className="list-disc pl-5 text-xs text-muted-foreground space-y-1 select-text">
                {(relevant.recommendations || []).map((r, i) => (
                  <li key={i}>{r}</li>
                ))}
              </ul>
            )}
          </Card>

          {HORIZONS.some((h) => (relevant.actions?.[h.key] || []).length > 0) && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {HORIZONS.map((h) => {
                const items = relevant.actions?.[h.key] || [];
                if (!items.length) return null;
                return (
                  <Card key={h.key} title={h.label}>
                    <ul className="list-disc pl-5 text-xs text-muted-foreground space-y-1">
                      {items.map((a, i) => (
                        <li key={i}>{a}</li>
                      ))}
                    </ul>
                  </Card>
                );
              })}
            </div>
          )}

          {(relevant.risks || []).length > 0 && (
            <Card title="Risks">
              <ul className="list-disc pl-5 text-xs text-warning space-y-1">
                {(relevant.risks || []).map((r, i) => (
                  <li key={i}>{r}</li>
                ))}
              </ul>
            </Card>
          )}
        </>
      )}
    </div>
  );
};

export default LandCropAdvisoryView;
