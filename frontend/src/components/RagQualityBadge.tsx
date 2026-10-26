import React from 'react'

export type RagQualityMetrics = {
  faithfulness: number | null
  answer_relevance: number | null
  context_precision: number | null
  computed?: boolean
  flags?: string[]
}

function barColor(score: number | null): string {
  if (score == null) return 'bg-muted-foreground/30'
  if (score >= 0.8) return 'bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.5)]'
  if (score >= 0.6) return 'bg-amber-400 shadow-[0_0_8px_rgba(251,191,36,0.5)]'
  return 'bg-rose-500 shadow-[0_0_8px_rgba(244,63,94,0.5)]'
}

function labelColor(score: number | null): string {
  if (score == null) return 'text-muted-foreground'
  if (score >= 0.8) return 'text-emerald-400'
  if (score >= 0.6) return 'text-amber-400'
  return 'text-rose-400'
}

function MetricBar({ name, score }: { name: string; score: number | null }) {
  const pct = score == null ? 0 : Math.max(0, Math.min(100, Math.round(score * 100)))
  return (
    <div className="min-w-0 flex-1">
      <div className="mb-1 flex items-center justify-between gap-2">
        <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground/80">{name}</span>
        <span className={`mono text-[10.5px] font-bold ${labelColor(score)}`}>
          {score == null ? 'n/a' : score.toFixed(2)}
        </span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-secondary/80 border border-border/40">
        <div className={`h-full rounded-full transition-all duration-500 ${barColor(score)}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}

export function RagQualityBadge({ metrics }: { metrics?: RagQualityMetrics | null }) {
  if (!metrics) return null
  return (
    <div className="rounded-xl border border-primary/25 bg-card/90 p-3.5 shadow-sm" data-testid="rag-quality-badge">
      <div className="mb-2.5 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="size-2 rounded-full bg-primary animate-pulse" />
          <p className="text-[11.5px] font-bold tracking-wide text-foreground">RAG Quality Verification</p>
        </div>
        <span className="mono text-[9.5px] font-medium text-primary/80 bg-primary/10 px-2 py-0.5 rounded border border-primary/20">
          {metrics.computed ? 'Ministral 8B Judge · Titan V2' : 'Incomplete'}
        </span>
      </div>
      <div className="flex flex-col gap-2.5 sm:flex-row sm:gap-3.5">
        <MetricBar name="Faithfulness" score={metrics.faithfulness} />
        <MetricBar name="Answer Relevance" score={metrics.answer_relevance} />
        <MetricBar name="Context Precision" score={metrics.context_precision} />
      </div>
    </div>
  )
}
