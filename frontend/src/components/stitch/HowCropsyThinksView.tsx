import React from "react";
import type { Phase7AdvisoryResult } from "@/lib/cropsy-api";
import { Badge, Card, Empty, Kv, PageHeader, ms, money } from "./ui";

interface HowCropsyThinksViewProps {
  selectedParcelId: string;
  onBackToChat: () => void;
  /** The most recent advisory response; its trace is shown verbatim. */
  lastResult?: Phase7AdvisoryResult | null;
}

type TraceStep = {
  step: string;
  tool_or_model: string;
  why: string;
  status: string;
  latency_ms: number;
  est_cost_usd: number;
  input_summary: string;
  output_summary: string;
};

const STATUS_TONE: Record<string, "ok" | "warn" | "bad"> = { ok: "ok", fallback: "warn", skipped: "warn", error: "bad", flagged: "warn" };

/** Route trace of the last question: every step, the model or tool used, why, latency and cost. Nothing here is static. */
export const HowCropsyThinksView: React.FC<HowCropsyThinksViewProps> = ({ onBackToChat, lastResult }) => {
  const obs: any = lastResult?.observability || {};
  const trace: TraceStep[] = obs.trace || [];

  return (
    <div className="w-full min-h-[calc(100vh-3.5rem)] bg-background text-foreground p-4 lg:p-6 flex flex-col gap-5">
      <PageHeader onBack={onBackToChat} crumb="How Cropsy thinks · route trace of your last question" />

      {!lastResult || !trace.length ? (
        <Empty>
          Ask a question in the chat first. This page then shows exactly which steps ran, which model or tool handled each one,
          why, and what it cost.
        </Empty>
      ) : (
        <>
          <Card title="Your question">
            <p className="text-sm text-foreground select-text">{lastResult.query}</p>
            <div className="flex flex-wrap gap-2 pt-1">
              <Badge tone="ok">route · {lastResult.route}</Badge>
              <Badge tone="ok">language · {obs.language || "n/a"}</Badge>
              <Badge tone={lastResult.verification?.status === "pass" ? "ok" : "warn"}>
                verification · {lastResult.verification?.status || "n/a"}
              </Badge>
              <Badge tone="ok">{lastResult.model_selected || "no model call"}</Badge>
              <Badge tone="ok">total {ms(obs.latency_ms)}</Badge>
              <Badge tone="ok">est. cost {money(obs.estimated_cost_usd)}</Badge>
            </div>
          </Card>

          <Card title={`Steps (${trace.length})`}>
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-left text-muted-foreground/70 font-mono border-b border-border">
                    <th className="py-1.5 pr-3">#</th>
                    <th className="pr-3">Step</th>
                    <th className="pr-3">Model / tool</th>
                    <th className="pr-3">Status</th>
                    <th className="pr-3 text-right">Latency</th>
                    <th className="text-right">Cost</th>
                  </tr>
                </thead>
                <tbody>
                  {trace.map((t, i) => (
                    <React.Fragment key={i}>
                      <tr className="border-b border-border/40 align-top">
                        <td className="py-2 pr-3 font-mono text-muted-foreground/70">{i + 1}</td>
                        <td className="pr-3 font-mono text-foreground">{t.step}</td>
                        <td className="pr-3 font-mono text-muted-foreground">{t.tool_or_model}</td>
                        <td className="pr-3">
                          <Badge tone={STATUS_TONE[t.status] || "ok"}>{t.status}</Badge>
                        </td>
                        <td className="pr-3 text-right font-mono">{ms(t.latency_ms)}</td>
                        <td className="text-right font-mono">{money(t.est_cost_usd)}</td>
                      </tr>
                      <tr className="border-b border-border/40">
                        <td />
                        <td colSpan={5} className="pb-2 text-[11.5px] text-muted-foreground leading-relaxed">
                          <span className="text-muted-foreground/70">Why: </span>
                          {t.why}
                          <br />
                          <span className="text-muted-foreground/70">In: </span>
                          {t.input_summary}
                          <br />
                          <span className="text-muted-foreground/70">Out: </span>
                          {t.output_summary}
                        </td>
                      </tr>
                    </React.Fragment>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <Card title="Model decision">
              <Kv k="Route" v={`${lastResult.route} (confidence ${(obs.reason || "").match(/confidence=([\d.]+)/)?.[1] ?? "n/a"})`} />
              <Kv k="Answer model" v={lastResult.model_selected || "none (handled without a model call)"} />
              <Kv k="Text chunks retrieved" v={obs.titan_text_chunks_retrieved ?? 0} />
              <Kv k="Photo matches" v={obs.titan_multimodal_matches ?? 0} />
              <Kv k="Evidence gap detected" v={String(!!obs.evidence_gap_detected)} />
              <Kv k="Tools called" v={(lastResult.tools_called || []).join(", ") || "none"} />
            </Card>
            <Card title="Verification">
              {(lastResult.verification?.checks || []).map((c) => (
                <div key={c.check} className="flex items-center justify-between text-xs border-b border-border/50 py-1">
                  <span className="font-mono text-muted-foreground">{c.check}</span>
                  <Badge tone={c.passed ? "ok" : "warn"}>{c.passed ? "passed" : "flagged"}</Badge>
                </div>
              ))}
              {(lastResult.verification?.flags || []).map((f) => (
                <p key={f} className="text-[11.5px] text-warning">
                  {f}
                </p>
              ))}
              {(lastResult.limitations || []).length > 0 && (
                <div className="pt-1">
                  <div className="text-[11px] text-muted-foreground/70 font-mono pb-1">LIMITATIONS</div>
                  <ul className="list-disc pl-4 text-[11.5px] text-muted-foreground space-y-0.5">
                    {(lastResult.limitations || []).map((l, i) => (
                      <li key={i}>{l}</li>
                    ))}
                  </ul>
                </div>
              )}
            </Card>
          </div>
        </>
      )}
    </div>
  );
};

export default HowCropsyThinksView;
