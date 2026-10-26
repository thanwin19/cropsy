import type { VisualReport as VR } from "@/lib/cropsy-api";

const tick = (ok: boolean) => (ok ? "✓" : "✗");

/** What Cropsy saw in the photo, before it named anything: the caption, the judge's verdict, and whether the reference photos agree. */
export function VisualReport({ report }: { report: VR }) {
  const j = report.judge;
  const a = report.agreement;
  const checks = j.checks ?? { morphology: true, severity: true, uncertainty: true, no_names: true };
  return (
    <section className="mb-3 rounded-xl border border-border bg-card/60 p-3" data-testid="visual-report">
      <h4 className="mb-2 text-xs font-semibold">📋 Visual report: what the photo shows <span className="font-normal text-muted-foreground">(described first, named later)</span></h4>
      <dl className="grid grid-cols-[110px_minmax(0,1fr)] gap-x-3 gap-y-1 text-[11.5px]">
        {report.caption.map((c) => (
          <div key={c.field} className="contents">
            <dt className="text-muted-foreground">{c.field}</dt>
            <dd className="font-medium">{c.value}</dd>
          </div>
        ))}
      </dl>
      <div className="mt-2 flex flex-wrap gap-1.5 text-[10.5px]">
        <span className={`rounded-full border px-2 py-0.5 font-mono ${j.passed ? "border-success/50 text-success" : "border-warning/50 text-warning"}`}>
          {j.passed ? "✅ Caption quality: PASSED" : "⚠ Caption has gaps"} · judge {report.models.judge}
        </span>
        <span className="rounded-full border border-border px-2 py-0.5 font-mono text-muted-foreground">
          Morphology {tick(checks.morphology)} · Severity {tick(checks.severity)} · Uncertainty {tick(checks.uncertainty)} · No names {tick(checks.no_names)}
        </span>
        {j.fixed_fields && j.fixed_fields.length > 0 && <span className="rounded-full border border-border px-2 py-0.5 font-mono text-muted-foreground">Judge rewrote: {j.fixed_fields.join(", ")}</span>}
        {j.retried && <span className="rounded-full border border-primary/50 px-2 py-0.5 font-mono text-primary">↻ Re-captioned once after the judge rejected the first</span>}
      </div>
      {a?.scores && a.scores.length > 0 && (
        <div className="mt-2 text-[11px]" data-testid="candidate-scores">
          <p className="mb-1 text-muted-foreground">Candidate scores (0 to 10, how well each condition fits the description){typeof a.gap === "number" ? `: lead ${a.gap}` : ""}</p>
          <ul className="grid gap-1">
            {a.scores.map((x) => (
              <li key={x.id} className="grid grid-cols-[minmax(0,1fr)_90px_28px] items-center gap-2">
                <span className="truncate">{x.label}</span>
                <span className="h-1.5 overflow-hidden rounded-full bg-muted"><span className="block h-full rounded-full bg-primary" style={{ width: `${x.score * 10}%` }} /></span>
                <span className="text-right font-mono">{x.score}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
      {a && (
        <p className="mt-2 text-[11.5px] text-muted-foreground">
          {a.status === "agree" && `The description also fits the nearest reference photos: ${a.reference_label}.`}
          {a.status === "uncertain" && `The description fits ${a.reference_label}, but also ${a.confusable_with ?? "a similar condition"} almost as well. The reference photos are the main evidence here; a closer photo of one affected leaf would help.`}
          {a.status === "not_confirmed" && `The description alone does not confirm ${a.reference_label}${a.caption_choice_label ? ` (it scores ${a.caption_choice_label} highest)` : ""}. The nearest reference photos are the main evidence; the description is shown so you can check it against the plant.`}
        </p>
      )}
    </section>
  );
}
