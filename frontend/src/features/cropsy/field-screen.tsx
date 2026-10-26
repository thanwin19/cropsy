import { useState } from "react";
import { useNavigate } from "@tanstack/react-router";
import { Printer } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { FieldHistoryView } from "@/components/stitch/FieldHistoryView";
import { FieldReportView } from "@/components/stitch/FieldReportView";
import { LandCropAdvisoryView } from "@/components/stitch/LandCropAdvisoryView";
import { THEN_MALAI_PARCELS } from "@/lib/parcels";
import { SectionStrip } from "./ui";
import { TodaySummary } from "./today-summary";
import { useCropsy } from "./store";

const TABS = ["Today", "Latest advisory", "History"] as const;
type Tab = (typeof TABS)[number];

/**
 * My field: one parcel's advisory. Today (village brief, what to do now, health, irrigation in mm with a pump window, soil test,
 * yield outlook, pest and disease watch with chemical and organic controls, N-P-K against target, village alerts),
 * Latest advisory (the most recent chat answer, printable) and History (2021-2025 seasons, NDVI trends, CSV export).
 */
export function FieldScreen() {
  const c = useCropsy();
  const navigate = useNavigate();
  const [tab, setTab] = useState<Tab>("Today");
  const parcel = c.parcelOrDefault;
  const backToChat = () => void navigate({ to: "/" });

  return (
    <div className="min-h-screen">
      <SectionStrip
        action={
          <div className="flex shrink-0 items-center gap-2">
            <Select value={parcel} onValueChange={c.selectParcel}>
              <SelectTrigger aria-label="Parcel" className="h-9 w-44 font-mono text-xs">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {THEN_MALAI_PARCELS.map((p) => (
                  <SelectItem key={p.id} value={p.id} className="font-mono text-xs">
                    {p.id} · {p.crop}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Button size="icon" variant="ghost" aria-label="Print field report" title="Print this field report" disabled={c.printing} onClick={() => void c.print()}>
              <Printer />
            </Button>
          </div>
        }
      >
        {TABS.map((x) => (
          <Button key={x} variant={tab === x ? "default" : "ghost"} size="sm" onClick={() => setTab(x)}>
            {x}
          </Button>
        ))}
      </SectionStrip>

      {tab === "Today" && (
        <>
          <div className="mx-auto max-w-6xl px-4 pt-4 md:px-6 md:pt-6">
            <div className="mb-4">
              <p className="text-xs text-muted-foreground">Parcel {parcel}</p>
              <p className="mt-1 text-sm">Field report · today</p>
            </div>
            <TodaySummary parcelId={parcel} />
            <h2 className="mb-1 text-sm font-semibold">Full advisory</h2>
            <p className="text-xs text-muted-foreground">The same field in detail: satellite map, irrigation planner, soil test, yield, pest and disease controls, fertiliser and village alerts.</p>
          </div>
          <FieldReportView selectedParcelId={parcel} onBackToChat={backToChat} onSelectParcel={c.selectParcel} onAskQuestion={(q) => void c.ask(q)} />
        </>
      )}
      {tab === "Latest advisory" && <LandCropAdvisoryView selectedParcelId={parcel} lastResult={c.lastResult} onBackToChat={backToChat} onAskQuestion={(q) => void c.ask(q)} />}
      {tab === "History" && <FieldHistoryView selectedParcelId={parcel} onBackToChat={backToChat} />}
    </div>
  );
}
