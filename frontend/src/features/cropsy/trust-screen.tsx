import { useState } from "react";
import { useNavigate } from "@tanstack/react-router";
import { Button } from "@/components/ui/button";
import { EvidenceSourcesView } from "@/components/stitch/EvidenceSourcesView";
import { HowCropsyThinksView } from "@/components/stitch/HowCropsyThinksView";
import { SectionStrip } from "./ui";
import { useCropsy } from "./store";

const TABS = ["Sources & evidence", "Route trace"] as const;
type Tab = (typeof TABS)[number];

/** Trust: what the latest answer was built from (documents, photo matches, verifier checks) and the step-by-step route it took. */
export function TrustScreen() {
  const c = useCropsy();
  const navigate = useNavigate();
  const [tab, setTab] = useState<Tab>("Sources & evidence");
  const back = () => void navigate({ to: "/" });
  return (
    <div className="min-h-screen">
      <SectionStrip>
        {TABS.map((x) => (
          <Button key={x} size="sm" variant={tab === x ? "default" : "ghost"} onClick={() => setTab(x)}>
            {x}
          </Button>
        ))}
      </SectionStrip>
      {tab === "Sources & evidence" ? (
        <EvidenceSourcesView selectedParcelId={c.parcelOrDefault} lastResult={c.lastResult} onBackToChat={back} />
      ) : (
        <HowCropsyThinksView selectedParcelId={c.parcelOrDefault} lastResult={c.lastResult} onBackToChat={back} />
      )}
    </div>
  );
}
