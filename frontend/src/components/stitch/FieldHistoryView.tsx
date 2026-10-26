import React, { useEffect, useState } from "react";
import { THEN_MALAI_PARCELS } from "@/lib/parcels";
import { fetchParcelHistory, type HistorySeason } from "@/lib/cropsy-api";
import { Badge, Card, DummyBadge, Empty, Kv, PageHeader } from "./ui";

interface FieldHistoryViewProps {
  selectedParcelId: string;
  onBackToChat: () => void;
}

/** Five seasons of yield, inputs and issues for the selected parcel. Source: backend /api/history (dummy dataset). */
export const FieldHistoryView: React.FC<FieldHistoryViewProps> = ({ selectedParcelId, onBackToChat }) => {
  const p = THEN_MALAI_PARCELS.find((x) => x.id === selectedParcelId) || THEN_MALAI_PARCELS[0];
  const [rows, setRows] = useState<HistorySeason[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [year, setYear] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    setRows(null);
    setError(null);
    fetchParcelHistory(p.id)
      .then((r) => {
        if (!live) return;
        setRows(r);
        setYear(r.length ? r[r.length - 1].year : null);
      })
      .catch((e) => live && setError(e.message || "Could not load history"));
    return () => {
      live = false;
    };
  }, [p.id]);

  const maxYield = rows ? Math.max(...rows.map((r) => Number(r.yield_value) || 0), 1) : 1;
  const sel = rows?.find((r) => r.year === year) || null;

  return (
    <div className="w-full min-h-[calc(100vh-3.5rem)] bg-background text-foreground p-4 lg:p-6 flex flex-col gap-5">
      <PageHeader onBack={onBackToChat} crumb={`Field history · ${p.id} · ${p.crop}`} right={<DummyBadge />} />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <Card title="This season (current)">
          <Kv k="Parcel" v={`${p.id} · ${p.name}`} />
          <Kv k="Crop" v={`${p.crop} (${p.variety})`} />
          <Kv k="Stage" v={`${p.stage.split(" - ")[0]} · ${p.daysAfterPlanting} days`} />
          <Kv k="Planted" v={p.plantingDate} />
          <Kv k="Area" v={`${p.areaHa} ha`} />
          <Kv k="Recorded issue" v={p.issueCode === "healthy" ? "None" : p.issue} />
          <Kv k="Last irrigation" v={`${p.irrigationDaysAgo} days ago`} />
          <Kv k="Last fertilizer" v={`${p.fertilizerDaysAgo} days ago`} />
        </Card>

        <Card
          className="lg:col-span-2"
          title={rows?.[0] ? `Yield by season (${rows[0].yield_unit})` : "Yield by season"}
        >
          {error && <Empty>{error}. Start the backend (port 8000) to load the history.</Empty>}
          {!error && !rows && <Empty>Loading history…</Empty>}
          {rows && (
            <div className="flex items-end gap-3 h-44 pt-2">
              {rows.map((r) => {
                const v = Number(r.yield_value) || 0;
                const active = r.year === year;
                return (
                  <button
                    key={r.year}
                    onClick={() => setYear(r.year)}
                    className="flex-1 flex flex-col items-center justify-end gap-1 h-full group"
                    title={`${r.year}: ${r.yield_value} ${r.yield_unit}`}
                  >
                    <span className="font-mono text-[11px] text-muted-foreground">{v}</span>
                    <div
                      className={`w-full rounded-t transition-all ${active ? "bg-success" : "bg-success/35 group-hover:bg-success/60"}`}
                      style={{ height: `${Math.max((v / maxYield) * 100, 4)}%` }}
                    />
                    <span className={`font-mono text-[11px] ${active ? "text-success" : "text-muted-foreground/70"}`}>{r.year}</span>
                    {r.major_issue && r.major_issue !== "none" && <span className="w-1.5 h-1.5 rounded-full bg-warning" title={r.major_issue} />}
                  </button>
                );
              })}
            </div>
          )}
          <p className="text-[11px] text-muted-foreground/70">A dot under a bar marks a season with a recorded issue. Click a bar for the details.</p>
        </Card>
      </div>

      {sel && (
        <Card title={`${sel.year} season`} right={<Badge tone="dummy">dummy</Badge>}>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-x-6">
            <Kv k="Crop" v={`${sel.crop} (${sel.variety})`} />
            <Kv k="Yield" v={`${sel.yield_value} ${sel.yield_unit}`} />
            <Kv k="Fertilizer programme" v={sel.fertilizer_used} />
            <Kv k="Irrigation" v={sel.irrigation_type} />
            <Kv k="Main issue" v={sel.major_issue === "none" ? "None recorded" : sel.major_issue} />
          </div>
        </Card>
      )}

      <p className="text-[11px] text-muted-foreground/70">
        All history here is generated sample data for the demo village. There is no real yield or input record behind it.
      </p>
    </div>
  );
};

export default FieldHistoryView;
