import { useEffect, useState } from 'react';
import { ArrowUpRight, CheckCircle2, Clock3, Filter, RefreshCw, Search, ShieldAlert } from 'lucide-react';
import { useNavigate } from '@tanstack/react-router';
import { CropsyShell, SectionLabel, StatusPill } from '@/components/cropsy-shell';
import {
  getApiSettings,
  getExecution,
  listExecutions,
  type ExecutionRecord,
  type FlaggedExecutionSummary,
} from '@/lib/cropsy-api';

function formatTimestamp(value?: string | null) {
  if (!value) return 'Time not recorded';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString();
}

function resolveState(item: FlaggedExecutionSummary): string {
  if (item.verification_result === 'pass') return 'completed';
  if (item.verification_result === 'needs_retry') return 'flagged';
  if (item.verification_result === 'flagged') return 'flagged';
  return item.verification_result || 'completed';
}

export default function Runs() {
  const navigate = useNavigate();
  const [query, setQuery] = useState('');
  const [active, setActive] = useState('all');
  const [items, setItems] = useState<FlaggedExecutionSummary[]>([]);
  const [loadingList, setLoadingList] = useState(true);
  const [listError, setListError] = useState('');
  const [selected, setSelected] = useState<ExecutionRecord | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  async function loadRuns() {
    setLoadingList(true);
    setListError('');
    try {
      const data = await listExecutions(['pass', 'flagged', 'needs_retry'], getApiSettings());
      setItems(data);
    } catch (err) {
      setListError(err instanceof Error ? err.message : 'Could not load execution runs.');
      setItems([]);
    } finally {
      setLoadingList(false);
    }
  }

  useEffect(() => {
    void loadRuns();
  }, []);

  useEffect(() => {
    if (selected) setError('');
  }, [selected]);

  const visible = items.filter((run) => {
    const state = resolveState(run);
    const matchesFilter =
      active === 'all' ||
      (active === 'completed' && state === 'completed') ||
      (active === 'flagged' && state === 'flagged');
    const matchesQuery = (run.user_request || '').toLowerCase().includes(query.toLowerCase());
    return matchesFilter && matchesQuery;
  });

  async function openRun(id: string) {
    setLoading(true);
    setError('');
    try {
      setSelected(await getExecution(id, getApiSettings()));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not open this run.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <CropsyShell>
      <div className="mx-auto max-w-[1180px] px-5 py-8 md:px-10 md:py-11">
        <div className="flex flex-col justify-between gap-5 sm:flex-row sm:items-end">
          <div>
            <SectionLabel>Run history / evidence ledger</SectionLabel>
            <h1 className="serif mt-2 text-[39px] leading-none tracking-[-.035em]">Execution runs</h1>
            <p className="mt-3 text-[13px] text-muted-foreground">
              Reopen any trace to inspect how the answer was assembled.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={() => void loadRuns()}
              className="focus-ring inline-flex items-center gap-2 rounded-xl border border-border bg-card px-3 py-2 text-[11px] font-bold text-muted-foreground hover:text-foreground"
            >
              <RefreshCw size={13} /> Refresh
            </button>
            <div className="flex items-center gap-2 rounded-lg border border-border bg-card px-3 py-2 text-[10px] text-muted-foreground">
              <Clock3 size={13} /> {items.length} {items.length === 1 ? 'record' : 'records'} in store
            </div>
          </div>
        </div>

        <div className="mt-9 grid gap-6 lg:grid-cols-[1fr_330px]">
          <section>
            <div className="mb-3 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div className="relative flex-1 sm:max-w-[360px]">
                <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
                <input
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder="Search questions"
                  className="focus-ring h-10 w-full rounded-xl border border-input bg-card pl-9 pr-3 text-[12px] outline-none"
                  data-testid="input-search-runs"
                />
              </div>
              <div className="flex items-center gap-1 rounded-xl bg-secondary p-1">
                <Filter size={13} className="ml-2 mr-1 text-muted-foreground" />
                {['all', 'completed', 'flagged'].map((filter) => (
                  <button
                    key={filter}
                    onClick={() => setActive(filter)}
                    className={`focus-ring rounded-lg px-2.5 py-1.5 text-[10px] font-bold capitalize ${
                      active === filter ? 'bg-card text-foreground shadow-sm' : 'text-muted-foreground'
                    }`}
                    data-testid={`button-filter-${filter}`}
                  >
                    {filter}
                  </button>
                ))}
              </div>
            </div>

            <div className="overflow-hidden rounded-2xl border border-border bg-card">
              {loadingList ? (
                <div className="space-y-3 p-5">
                  <div className="skeleton h-4 w-2/3 rounded" />
                  <div className="skeleton h-16 rounded-xl" />
                </div>
              ) : listError ? (
                <div className="p-5 text-[12px] text-destructive">{listError}</div>
              ) : visible.length === 0 ? (
                <div className="flex min-h-[250px] flex-col items-center justify-center px-6 text-center">
                  <Search size={20} className="mb-3 text-muted-foreground" />
                  <p className="text-[13px] font-bold">No matching traces</p>
                  <p className="mt-1 text-[11px] text-muted-foreground">Try a different parcel, village, or status.</p>
                </div>
              ) : (
                visible.map((run) => {
                  const state = resolveState(run);
                  const taskCount = Object.keys(run.task_verification_results || {}).length;
                  return (
                    <button
                      key={run.execution_id}
                      onClick={() => openRun(run.execution_id)}
                      className="focus-ring group flex w-full items-start gap-4 border-b border-border p-4 text-left last:border-0 hover:bg-secondary/35 md:p-5"
                      data-testid={`button-open-run-${run.execution_id}`}
                    >
                      <span
                        className={`mt-1 grid size-8 shrink-0 place-items-center rounded-lg ${
                          state === 'flagged'
                            ? 'bg-amber-500/12 text-amber-700'
                            : 'bg-primary/10 text-primary'
                        }`}
                      >
                        {state === 'flagged' ? <ShieldAlert size={16} /> : <CheckCircle2 size={16} />}
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="mb-1 flex flex-wrap items-center gap-2">
                          <StatusPill status={state}>
                            {state === 'flagged' ? 'Review needed' : 'Verified'}
                          </StatusPill>
                          <span className="text-[10px] text-muted-foreground">
                            {formatTimestamp(run.timestamp || run.created_at)}
                          </span>
                        </span>
                        <span className="block text-[13px] font-semibold leading-relaxed">
                          {run.user_request}
                        </span>
                        <span className="mt-1 block text-[10px] text-muted-foreground">
                          ID: <span className="font-mono">{run.execution_id.slice(0, 8)}</span>
                          {taskCount > 0 && (
                            <>
                              <span className="mx-1 text-border">·</span>
                              {taskCount} {taskCount === 1 ? 'task' : 'tasks'}
                            </>
                          )}
                          {run.triggered_rules && run.triggered_rules.length > 0 && (
                            <>
                              <span className="mx-1 text-border">·</span>
                              {run.triggered_rules.join(', ')}
                            </>
                          )}
                        </span>
                      </span>
                      <ArrowUpRight
                        size={16}
                        className="mt-1 text-muted-foreground transition-transform group-hover:-translate-y-0.5 group-hover:translate-x-0.5"
                      />
                    </button>
                  );
                })
              )}
            </div>
          </section>

          <aside className="rounded-2xl border border-border bg-card p-5">
            <SectionLabel>Selected trace</SectionLabel>
            {loading ? (
              <div className="mt-5 space-y-3">
                <div className="skeleton h-4 w-2/3 rounded" />
                <div className="skeleton h-16 rounded-xl" />
                <div className="skeleton h-4 w-1/2 rounded" />
              </div>
            ) : error ? (
              <div className="mt-6 rounded-xl bg-destructive/10 p-3 text-[11px] text-destructive">{error}</div>
            ) : selected ? (
              <div className="mt-4">
                <StatusPill status={selected.verification_result.includes('flagged') ? 'flagged' : 'completed'}>
                  {selected.verification_result.includes('flagged') ? 'Review needed' : 'Verified trace'}
                </StatusPill>
                <p className="mt-4 text-[13px] leading-relaxed">{selected.final_answer}</p>
                <div className="mt-5 grid grid-cols-2 gap-3 border-t border-border pt-4">
                  <div>
                    <p className="mono text-[9px] uppercase text-muted-foreground">Latency</p>
                    <p className="mono mt-1 text-[12px]">{selected.total_latency_ms} ms</p>
                  </div>
                  <div>
                    <p className="mono text-[9px] uppercase text-muted-foreground">Cost</p>
                    <p className="mono mt-1 text-[12px]">${(selected.total_estimated_cost || 0).toFixed(3)}</p>
                  </div>
                </div>
                <button
                  onClick={() => void navigate({ to: '/' })}
                  className="focus-ring mt-5 flex w-full items-center justify-center gap-2 rounded-xl bg-primary px-3 py-3 text-[11px] font-bold text-primary-foreground"
                  data-testid="button-reopen-workspace"
                >
                  Open in workspace <ArrowUpRight size={14} />
                </button>
              </div>
            ) : (
              <div className="mt-6 rounded-xl bg-secondary/60 p-4">
                <p className="text-[12px] font-semibold">Choose a trace</p>
                <p className="mt-1 text-[11px] leading-relaxed text-muted-foreground">
                  Select a run from the ledger to preview its answer and operational metrics.
                </p>
              </div>
            )}
          </aside>
        </div>
      </div>
    </CropsyShell>
  );
}