import { useEffect, useState } from 'react';
import { ArrowUpRight, RefreshCw, ShieldAlert, ShieldX } from 'lucide-react';
import { CropsyShell, SectionLabel, StatusPill } from '@/components/cropsy-shell';
import { RouteTraceDetail } from '@/components/RouteTraceDetail';
import { OfficerReview } from '@/components/OfficerReview';
import {
  getApiSettings,
  getExecution,
  listFlaggedExecutions,
  listMissedQuestions,
  listFeedback,
  type FeedbackRow,
  type MissedQuestion,
  type ExecutionRecord,
  type FlaggedExecutionSummary,
} from '@/lib/cropsy-api';

function statusOf(item: FlaggedExecutionSummary) {
  return item.verification_result === 'needs_retry' ? 'needs_retry' : 'flagged';
}

function formatTimestamp(value?: string | null) {
  if (!value) return 'Time not recorded';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString();
}

export default function FlaggedCases() {
  const [items, setItems] = useState<FlaggedExecutionSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<ExecutionRecord | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState('');
  const [missed, setMissed] = useState<MissedQuestion[]>([]);
  const [feedback, setFeedback] = useState<FeedbackRow[]>([]);

  async function loadList() {
    setLoading(true);
    setError('');
    try {
      const next = await listFlaggedExecutions(getApiSettings());
      setItems(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load flagged cases.');
      setItems([]);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadList();
    void listMissedQuestions(getApiSettings()).then(setMissed).catch(() => setMissed([]));
    void listFeedback(getApiSettings()).then(setFeedback).catch(() => setFeedback([]));
  }, []);

  async function openCase(id: string) {
    setSelectedId(id);
    setDetailLoading(true);
    setDetailError('');
    try {
      setDetail(await getExecution(id, getApiSettings()));
    } catch (err) {
      setDetail(null);
      setDetailError(err instanceof Error ? err.message : 'Could not open this execution.');
    } finally {
      setDetailLoading(false);
    }
  }

  return (
    <CropsyShell>
      <div className="mx-auto max-w-[1180px] px-5 py-8 md:px-10 md:py-11">
        <div className="flex flex-col justify-between gap-5 sm:flex-row sm:items-end">
          <div>
            <SectionLabel>Verifier / critic review</SectionLabel>
            <h1 className="serif mt-2 text-[39px] leading-none tracking-[-.035em]">Flagged Cases</h1>
            <p className="mt-3 max-w-[620px] text-[13px] text-muted-foreground">
              Past executions whose critic returned <span className="font-semibold text-amber-700">flagged</span> or{' '}
              <span className="font-semibold text-red-700">needs_retry</span> — not just the current query.
            </p>
          </div>
          <button
            onClick={() => void loadList()}
            className="focus-ring inline-flex items-center gap-2 rounded-xl border border-border bg-card px-3 py-2 text-[11px] font-bold text-muted-foreground hover:text-foreground"
            data-testid="button-refresh-flagged"
          >
            <RefreshCw size={13} /> Refresh
          </button>
        </div>

        <section className="mt-8 rounded-2xl border border-border bg-card p-5" data-testid="missed-questions">
          <SectionLabel>Questions Cropsy did not understand</SectionLabel>
          <p className="mt-1 text-[11px] text-muted-foreground">Asked but not recognised as a farm question, so Cropsy asked for detail instead of guessing. Use these to add new guidance.</p>
          {missed.length === 0 ? (
            <p className="mt-3 text-[12px] text-muted-foreground">None yet.</p>
          ) : (
            <ul className="mt-3 divide-y divide-border text-[12px]">
              {missed.map((m) => (
                <li key={m.time + m.query} className="flex items-baseline justify-between gap-3 py-1.5">
                  <span className="min-w-0 break-words font-medium">{m.query}</span>
                  <span className="shrink-0 text-[10px] text-muted-foreground">{m.parcel_id ? `${m.parcel_id} · ` : ''}{formatTimestamp(m.time)}</span>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="mt-6 rounded-2xl border border-border bg-card p-5" data-testid="farmer-feedback">
          <SectionLabel>Farmer feedback for officer review</SectionLabel>
          <p className="mt-1 text-[11px] text-muted-foreground">Thumbs on answers, from farmers who agreed to help improve Cropsy. Not-helpful answers are listed first: an officer should check them and correct the guidance.</p>
          {feedback.length === 0 ? (
            <p className="mt-3 text-[12px] text-muted-foreground">None yet.</p>
          ) : (
            <ul className="mt-3 divide-y divide-border text-[12px]">
              {[...feedback].sort((a, b) => Number(a.helpful) - Number(b.helpful)).map((f) => (
                <li key={f.time + f.query} className="flex items-baseline justify-between gap-3 py-1.5">
                  <span className="min-w-0 break-words"><span className="mr-2">{f.helpful ? '👍' : '👎'}</span><span className="font-medium">{f.query}</span></span>
                  <span className="shrink-0 text-[10px] text-muted-foreground">{f.confidence ? `${f.confidence} · ` : ''}{f.parcel_id ? `${f.parcel_id} · ` : ''}{formatTimestamp(f.time)}</span>
                </li>
              ))}
            </ul>
          )}
        </section>

        <OfficerReview feedback={feedback} />

        <div className="mt-9 grid gap-6 lg:grid-cols-[1fr_minmax(320px,0.95fr)]">
          <section>
            <div className="overflow-hidden rounded-2xl border border-border bg-card">
              {loading ? (
                <div className="space-y-3 p-5">
                  <div className="skeleton h-4 w-2/3 rounded" />
                  <div className="skeleton h-16 rounded-xl" />
                  <div className="skeleton h-16 rounded-xl" />
                </div>
              ) : error ? (
                <div className="p-5 text-[12px] text-destructive">{error}</div>
              ) : items.length === 0 ? (
                <div className="flex min-h-[280px] flex-col items-center justify-center px-6 text-center" data-testid="empty-flagged-cases">
                  <ShieldAlert size={22} className="mb-3 text-muted-foreground" />
                  <p className="text-[13px] font-bold">No flagged cases</p>
                  <p className="mt-1 max-w-[360px] text-[11px] text-muted-foreground">
                    No stored executions currently have verification_result flagged or needs_retry. Run a query that hits a critic rule, then refresh.
                  </p>
                </div>
              ) : (
                items.map((item) => {
                  const status = statusOf(item);
                  const active = selectedId === item.execution_id;
                  return (
                    <button
                      key={item.execution_id}
                      onClick={() => void openCase(item.execution_id)}
                      className={`focus-ring group flex w-full items-start gap-4 border-b border-border p-4 text-left last:border-0 hover:bg-secondary/35 md:p-5 ${active ? 'bg-secondary/50' : ''}`}
                      data-testid={`button-open-flagged-${item.execution_id}`}
                    >
                      <span
                        className={`mt-1 grid size-8 shrink-0 place-items-center rounded-lg ${
                          status === 'needs_retry' ? 'bg-red-500/12 text-red-700' : 'bg-amber-500/12 text-amber-700'
                        }`}
                      >
                        {status === 'needs_retry' ? <ShieldX size={16} /> : <ShieldAlert size={16} />}
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="mb-1 flex flex-wrap items-center gap-2">
                          <StatusPill status={status}>{status === 'needs_retry' ? 'Needs retry' : 'Flagged'}</StatusPill>
                          <span className="text-[10px] text-muted-foreground">{formatTimestamp(item.timestamp || item.created_at)}</span>
                        </span>
                        <span className="block text-[13px] font-semibold leading-relaxed">{item.user_request}</span>
                        <span className="mt-2 flex flex-wrap gap-1.5">
                          {(item.triggered_rules || []).map((rule) => (
                            <span key={rule} className="mono rounded-md bg-secondary px-2 py-0.5 text-[10px] text-secondary-foreground">
                              {rule}
                            </span>
                          ))}
                        </span>
                        {(item.reasons || []).length > 0 ? (
                          <span className="mt-2 block text-[11px] leading-relaxed text-muted-foreground">
                            {item.reasons!.join(' ')}
                          </span>
                        ) : null}
                      </span>
                      <ArrowUpRight size={16} className="mt-1 text-muted-foreground transition-transform group-hover:-translate-y-0.5 group-hover:translate-x-0.5" />
                    </button>
                  );
                })
              )}
            </div>
          </section>

          <aside>
            {detailLoading ? (
              <div className="rounded-2xl border border-border bg-card p-5">
                <SectionLabel>Selected trace</SectionLabel>
                <div className="mt-5 space-y-3">
                  <div className="skeleton h-4 w-2/3 rounded" />
                  <div className="skeleton h-16 rounded-xl" />
                  <div className="skeleton h-4 w-1/2 rounded" />
                </div>
              </div>
            ) : detailError ? (
              <div className="rounded-2xl border border-border bg-card p-5 text-[12px] text-destructive">{detailError}</div>
            ) : detail ? (
              <RouteTraceDetail record={detail} />
            ) : (
              <div className="rounded-2xl border border-border bg-card p-5">
                <SectionLabel>Selected trace</SectionLabel>
                <div className="mt-6 rounded-xl bg-secondary/60 p-4">
                  <p className="text-[12px] font-semibold">Choose a flagged case</p>
                  <p className="mt-1 text-[11px] leading-relaxed text-muted-foreground">
                    Open a row to inspect the same route-trace used on the live workspace: model/tool per step, cost, latency, confidence, and citations.
                  </p>
                </div>
              </div>
            )}
          </aside>
        </div>
      </div>
    </CropsyShell>
  );
}
