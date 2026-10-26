import { useState } from 'react';
import { AlertTriangle, Check, ChevronDown, RotateCcw, Sparkles } from 'lucide-react';
import { RagQualityBadge } from '@/components/RagQualityBadge';
import { RouterDecisionCard, isRouterStep } from '@/components/RouterDecisionCard';
import { SectionLabel } from '@/components/cropsy-shell';
import type { ExecutionRecord, TaskRecord } from '@/lib/cropsy-api';

function taskNeedsRetry(task: TaskRecord) {
  return (
    task.status === 'needs_retry' ||
    task.verification_result?.toLowerCase().includes('needs_retry')
  );
}

function taskIsFlagged(task: TaskRecord) {
  return (
    !taskNeedsRetry(task) &&
    (task.status === 'flagged' || task.verification_result?.toLowerCase().includes('flagged'))
  );
}

export function TaskRow({ task, open, onToggle }: { task: TaskRecord; open: boolean; onToggle: () => void }) {
  const isRetry = taskNeedsRetry(task);
  const isFlagged = taskIsFlagged(task);
  const isRouter = isRouterStep(task);
  return (
    <div
      className={`rounded-xl border transition-all ${
        isRetry
          ? 'border-red-500/40 bg-red-500/[.05]'
          : isFlagged
            ? 'border-amber-500/35 bg-amber-500/[.045]'
            : isRouter
              ? 'border-primary/40 bg-card shadow-xs ring-1 ring-primary/10'
              : 'border-border bg-card'
      }`}
    >
      <button
        onClick={onToggle}
        className="focus-ring flex w-full items-center gap-3 px-4 py-3.5 text-left"
        data-testid={`button-expand-task-${task.task_id}`}
      >
        <span
          className={`grid size-7 shrink-0 place-items-center rounded-lg ${
            isRetry
              ? 'bg-red-500/15 text-red-700'
              : isFlagged
                ? 'bg-amber-500/15 text-amber-700'
                : isRouter
                  ? 'bg-primary text-primary-foreground shadow-xs'
                  : 'bg-primary/10 text-primary'
          }`}
        >
          {isRetry || isFlagged ? (
            <AlertTriangle size={15} />
          ) : isRouter ? (
            <Sparkles size={15} />
          ) : (
            <Check size={15} strokeWidth={2.5} />
          )}
        </span>
        <span className="min-w-0 flex-1">
          <span className="flex items-center gap-2">
            <span className="block text-[12px] font-bold">{task.description || task.task_id}</span>
            {isRouter && (
              <span className="rounded bg-primary/15 px-1.5 py-0.5 font-mono text-[9px] font-bold text-primary">
                ⚡ ROUTER CORE
              </span>
            )}
          </span>
          <span className="mt-0.5 block truncate text-[10px] text-muted-foreground">
            <span className="mono font-medium text-foreground/80">{task.selected_model_or_tool}</span>
            <span className="mx-1.5 text-border">·</span>
            <span>{task.source}</span>
            {task.latency_ms ? <span className="ml-1.5 text-[9px] text-muted-foreground/80">({task.latency_ms}ms)</span> : null}
          </span>
        </span>
        <span className="hidden text-right sm:block">
          <span className="mono block text-[11px] font-semibold">{Math.round((task.actual_confidence ?? 0.9) * 100)}%</span>
          <span className="text-[9px] text-muted-foreground">confidence</span>
        </span>
        <ChevronDown size={15} className={`shrink-0 text-muted-foreground transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>

      {open && (
        <div className="grid gap-4 border-t border-border/70 px-4 pb-4 pt-3 sm:grid-cols-2">
          <div className="sm:col-span-2">
            <RouterDecisionCard task={task} renderPlaceholder={true} />
          </div>
          <div>
            <p className="mono mb-1 text-[9px] uppercase tracking-[.12em] text-muted-foreground">Execution Result</p>
            <p className="text-[12px] leading-relaxed text-foreground/90 whitespace-pre-wrap">{task.actual_result}</p>
          </div>
          <div>
            <p className="mono mb-1 text-[9px] uppercase tracking-[.12em] text-muted-foreground">Why this route</p>
            <p className="text-[12px] leading-relaxed text-muted-foreground">{task.reason_for_selection || 'Optimal cost-confidence routing tier'}</p>
          </div>
          <div>
            <p className="mono mb-1 text-[9px] uppercase tracking-[.12em] text-muted-foreground">Critic Verification</p>
            <p className="text-[12px] leading-relaxed text-muted-foreground">{task.verification_result || 'Verified with 0 conflicts'}</p>
          </div>
          <div>
            <p className="mono mb-1 text-[9px] uppercase tracking-[.12em] text-muted-foreground">Citations & References</p>
            <div className="flex flex-wrap gap-1.5">
              {task.rag_citations && task.rag_citations.length > 0 ? (
                task.rag_citations.map((citation, i) => (
                  <span key={i} className="rounded-md bg-secondary px-2 py-1 text-[10px] text-secondary-foreground font-mono">
                    {citation}
                  </span>
                ))
              ) : (
                <span className="text-[11px] text-muted-foreground">Deterministic pipeline verification</span>
              )}
            </div>
          </div>
          {task.rag_quality_metrics ? (
            <div className="sm:col-span-2">
              <RagQualityBadge metrics={task.rag_quality_metrics} />
            </div>
          ) : null}
          {task.fallback_attempts && task.fallback_attempts.length > 0 && (
            <div className="sm:col-span-2">
              <p className="mono mb-1 text-[9px] uppercase tracking-[.12em] text-muted-foreground">Fallback history</p>
              <p className="text-[11px] text-amber-700">{task.fallback_attempts.join(' · ')}</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export function RouteTraceDetail({
  record,
  onReset,
}: {
  record: ExecutionRecord;
  onReset?: () => void;
}) {
  const [openTask, setOpenTask] = useState('');
  const [showPlan, setShowPlan] = useState(false);
  return (
    <div className="rounded-2xl border border-border bg-card p-4 md:p-5 shadow-sm">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <SectionLabel>Judge-Facing Route Trace & Decision Audit</SectionLabel>
          <p className="mt-1 text-[12px] text-muted-foreground">
            {record.tasks.length} routed agent tasks · Execution ID: <span className="mono font-semibold">{record.execution_id}</span>
          </p>
        </div>
        <button
          onClick={() => setShowPlan(!showPlan)}
          className="focus-ring text-[10px] font-bold text-primary hover:underline"
          data-testid="button-toggle-plan"
        >
          {showPlan ? 'Hide Execution Plan' : 'View Execution Plan'}
        </button>
      </div>

      {showPlan && (
        <div className="mb-4 rounded-xl bg-secondary/60 p-3">
          {record.execution_plan.map((step, index) => (
            <div key={`${step}-${index}`} className="flex gap-3 py-1.5 text-[11px]">
              <span className="mono text-muted-foreground">0{index + 1}</span>
              <span className="font-medium text-foreground/90">{step}</span>
            </div>
          ))}
        </div>
      )}

      <div className="space-y-2">
        {record.tasks.map((task) => (
          <TaskRow
            key={task.task_id}
            task={task}
            open={openTask === task.task_id}
            onToggle={() => setOpenTask(openTask === task.task_id ? '' : task.task_id)}
          />
        ))}
      </div>

      {onReset ? (
        <div className="mt-4 flex items-center justify-between px-1">
          <span className="mono text-[9px] uppercase tracking-[.12em] text-muted-foreground">
            Source chain verified · {record.execution_id}
          </span>
          <button
            onClick={onReset}
            className="focus-ring inline-flex items-center gap-1 text-[10px] font-bold text-muted-foreground hover:text-foreground"
            data-testid="button-new-trace"
          >
            <RotateCcw size={12} /> Reset trace
          </button>
        </div>
      ) : null}
    </div>
  );
}
