import React, { useState } from 'react';
import {
  AlertCircle,
  CheckCircle2,
  ChevronDown,
  DollarSign,
  Layers,
  Scale,
  Sliders,
  Sparkles,
  Trophy,
  Zap,
} from 'lucide-react';
import type { TaskRecord } from '@/lib/cropsy-api';

export interface RouterCandidate {
  id: string;
  aliases: string[];
  name: string;
  shortName: string;
  tier: string;
  tierCategory: 'cheap_open' | 'proprietary_escalation' | 'proprietary_primary';
  costUsd: number;
  latencyMs: number;
  baselineConfidence: number;
}

export const KNOWN_MODEL_METADATA: Record<string, {
  name: string;
  shortName: string;
  tier: string;
  tierCategory: 'cheap_open' | 'proprietary_escalation' | 'proprietary_primary';
  costUsd: number;
  latencyMs: number;
  baselineConfidence: number;
}> = {
  'mistral.ministral-3-3b-instruct': {
    name: 'Ministral 3B Instruct',
    shortName: 'Ministral 3B',
    tier: 'Tier 1 · Cheap Open-Weight (Bedrock ap-south-1)',
    tierCategory: 'cheap_open',
    costUsd: 0.00015,
    latencyMs: 250,
    baselineConfidence: 0.88,
  },
  'mistral.ministral-3-8b-instruct': {
    name: 'Ministral 8B Instruct',
    shortName: 'Ministral 8B',
    tier: 'Tier 2 · Structured Reasoning (Bedrock ap-south-1)',
    tierCategory: 'cheap_open',
    costUsd: 0.00045,
    latencyMs: 400,
    baselineConfidence: 0.91,
  },
  'apac.amazon.nova-micro-v1:0': {
    name: 'Amazon Nova Micro',
    shortName: 'Nova Micro',
    tier: 'Tier 3 · Bedrock Frontier Fast (ap-south-1)',
    tierCategory: 'proprietary_escalation',
    costUsd: 0.00080,
    latencyMs: 300,
    baselineConfidence: 0.94,
  },
  'apac.amazon.nova-lite-v1:0': {
    name: 'Amazon Nova Lite',
    shortName: 'Nova Lite (Multimodal)',
    tier: 'Tier 4 · Bedrock Frontier Multimodal (ap-south-1)',
    tierCategory: 'proprietary_primary',
    costUsd: 0.00180,
    latencyMs: 650,
    baselineConfidence: 0.97,
  },
  'amazon.nova-micro-v1:0': {
    name: 'Amazon Nova Micro',
    shortName: 'Nova Micro',
    tier: 'Tier 3 · Bedrock Frontier Fast (ap-south-1)',
    tierCategory: 'proprietary_escalation',
    costUsd: 0.00080,
    latencyMs: 300,
    baselineConfidence: 0.94,
  },
  'amazon.nova-lite-v1:0': {
    name: 'Amazon Nova Lite',
    shortName: 'Nova Lite (Multimodal)',
    tier: 'Tier 4 · Bedrock Frontier Multimodal (ap-south-1)',
    tierCategory: 'proprietary_primary',
    costUsd: 0.00180,
    latencyMs: 650,
    baselineConfidence: 0.97,
  },
};

/**
 * Resolves a model identifier to its active reported endpoint name (e.g. apac.amazon.nova-micro-v1:0).
 */
export function resolveModelDisplayName(rawModelId: string): string {
  const cleanId = (rawModelId || '').trim();
  if (cleanId === 'amazon.nova-micro-v1:0' || cleanId === 'apac.amazon.nova-micro-v1:0') {
    return 'Amazon Nova Micro';
  }
  if (cleanId === 'amazon.nova-lite-v1:0' || cleanId === 'apac.amazon.nova-lite-v1:0') {
    return 'Amazon Nova Lite';
  }
  if (KNOWN_MODEL_METADATA[cleanId]) {
    return KNOWN_MODEL_METADATA[cleanId].name;
  }
  return cleanId || 'Unknown Model';
}

export function resolveModelShortName(rawModelId: string): string {
  const cleanId = (rawModelId || '').trim();
  if (cleanId === 'amazon.nova-micro-v1:0' || cleanId === 'apac.amazon.nova-micro-v1:0') {
    return 'Nova Micro';
  }
  if (cleanId === 'amazon.nova-lite-v1:0' || cleanId === 'apac.amazon.nova-lite-v1:0') {
    return 'Nova Lite';
  }
  if (KNOWN_MODEL_METADATA[cleanId]) {
    return KNOWN_MODEL_METADATA[cleanId].shortName;
  }
  return cleanId || 'Unknown';
}

export const ROUTER_CANDIDATES: RouterCandidate[] = [
  {
    id: 'mistral.ministral-3-3b-instruct',
    aliases: ['ministral-3b', 'mistral-3-3b', 'ministral 3b instruct', 'ministral 3b', 'ministral_3b'],
    name: 'Ministral 3B Instruct',
    shortName: 'Ministral 3B',
    tier: 'Tier 1 · Cheap Open-Weight (Bedrock ap-south-1)',
    tierCategory: 'cheap_open',
    costUsd: 0.00015,
    latencyMs: 250,
    baselineConfidence: 0.88,
  },
  {
    id: 'mistral.ministral-3-8b-instruct',
    aliases: ['ministral-8b', 'mistral-3-8b', 'ministral 8b instruct', 'ministral 8b', 'ministral_8b'],
    name: 'Ministral 8B Instruct',
    shortName: 'Ministral 8B',
    tier: 'Tier 2 · Structured Reasoning (Bedrock ap-south-1)',
    tierCategory: 'cheap_open',
    costUsd: 0.00045,
    latencyMs: 400,
    baselineConfidence: 0.91,
  },
  {
    id: 'apac.amazon.nova-micro-v1:0',
    aliases: ['nova-micro', 'nova micro', 'amazon.nova-micro-v1:0', 'apac.amazon.nova-micro-v1:0'],
    name: 'Amazon Nova Micro',
    shortName: 'Nova Micro',
    tier: 'Tier 3 · Bedrock Frontier Fast (ap-south-1)',
    tierCategory: 'proprietary_escalation',
    costUsd: 0.00080,
    latencyMs: 300,
    baselineConfidence: 0.94,
  },
  {
    id: 'apac.amazon.nova-lite-v1:0',
    aliases: ['nova-lite', 'nova lite', 'amazon.nova-lite-v1:0', 'apac.amazon.nova-lite-v1:0'],
    name: 'Amazon Nova Lite',
    shortName: 'Nova Lite (Multimodal)',
    tier: 'Tier 4 · Bedrock Frontier Multimodal (ap-south-1)',
    tierCategory: 'proprietary_primary',
    costUsd: 0.00180,
    latencyMs: 650,
    baselineConfidence: 0.97,
  },
];

export const FRONTIER_MODEL_COST = 0.00180; // Amazon Nova Lite baseline cost
export const DEFAULT_ROUTER_THRESHOLD = 0.85;

/**
 * Checks if a task represents or went through the Model Router.
 */
export function isRouterStep(task: TaskRecord): boolean {
  if (task.task_id === 'model_router' || task.task_id === 'router') return true;
  if (task.candidate_models_considered && task.candidate_models_considered.length > 0) return true;

  const confKeys = Object.keys(task.predicted_confidences || {});
  if (
    confKeys.some((k) =>
      k.toLowerCase().includes('ministral') ||
      k.toLowerCase().includes('nova') ||
      k.toLowerCase().includes('mistral') ||
      k.toLowerCase().includes('bedrock')
    )
  ) {
    return true;
  }

  const tool = (task.selected_model_or_tool || '').toLowerCase();
  if (
    tool.includes('ministral') ||
    tool.includes('nova') ||
    tool.includes('router') ||
    tool.includes('confidence-predictor')
  ) {
    return true;
  }

  return false;
}

interface RouterDecisionCardProps {
  task: TaskRecord;
  threshold?: number;
  renderPlaceholder?: boolean;
}

export function RouterDecisionCard({
  task,
  threshold = DEFAULT_ROUTER_THRESHOLD,
  renderPlaceholder = true,
}: RouterDecisionCardProps) {
  const [showFeatures, setShowFeatures] = useState(false);

  // Check if this step requires the router
  const isModelStep = isRouterStep(task);

  if (!isModelStep) {
    if (!renderPlaceholder) return null;
    return (
      <div className="flex items-center gap-2 rounded-xl border border-border/60 bg-muted/20 px-3.5 py-2.5 text-[11px] text-muted-foreground">
        <span className="size-2 rounded-full bg-slate-400" />
        <span className="font-semibold text-foreground/80">Deterministic Tool Step</span>
        <span className="text-border">·</span>
        <span>Bypasses model router (zero model token cost, deterministic execution)</span>
      </div>
    );
  }

  // Identify winning model directly from backend data (selected_model_api_name, selected_model_name, selected_model_or_tool)
  const winningRaw =
    (task as any).selected_model_api_name ||
    task.selected_model_name ||
    task.selected_model_or_tool ||
    'mistral.ministral-3-3b-instruct';

  const winningModelDisplayName = resolveModelDisplayName(winningRaw);
  const winningModelShortName = resolveModelShortName(winningRaw);
  const winningCandidateMeta =
    KNOWN_MODEL_METADATA[winningRaw] ||
    KNOWN_MODEL_METADATA[winningModelDisplayName] ||
    ROUTER_CANDIDATES.find((c) => c.id === winningRaw || c.aliases.includes(winningRaw)) ||
    ROUTER_CANDIDATES[0];

  // Resolve candidate models dynamically from backend data:
  // 1. task.candidate_models_considered
  // 2. Object.keys(task.predicted_confidences)
  // 3. ROUTER_CANDIDATES list as fallback
  const rawCandidateIds: string[] =
    task.candidate_models_considered && task.candidate_models_considered.length > 0
      ? task.candidate_models_considered
      : Object.keys(task.predicted_confidences || {}).length > 0
      ? Object.keys(task.predicted_confidences)
      : ROUTER_CANDIDATES.map((c) => c.id);

  // Normalize candidate IDs to ensure uniqueness while preserving backend order
  const uniqueCandidateIds = Array.from(new Set(rawCandidateIds));

  const candidateScores = uniqueCandidateIds.map((rawId) => {
    const displayName = resolveModelDisplayName(rawId);
    const shortName = resolveModelShortName(rawId);
    const meta =
      KNOWN_MODEL_METADATA[rawId] ||
      KNOWN_MODEL_METADATA[displayName] || {
        name: displayName,
        shortName: shortName,
        tier: 'Model Route Tier',
        tierCategory: 'cheap_open' as const,
        costUsd: 0.00015,
        latencyMs: 300,
        baselineConfidence: 0.88,
      };

    let score: number | undefined;
    const preds = task.predicted_confidences || {};

    // 1. Direct match
    if (preds[rawId] !== undefined) {
      score = typeof preds[rawId] === 'number' ? preds[rawId] : parseFloat(String(preds[rawId]));
    } else if (preds[displayName] !== undefined) {
      score = typeof preds[displayName] === 'number' ? preds[displayName] : parseFloat(String(preds[displayName]));
    } else {
      // 2. Fuzzy match across keys in predicted_confidences
      for (const [key, val] of Object.entries(preds)) {
        const kLower = key.toLowerCase();
        if (
          kLower === rawId.toLowerCase() ||
          kLower === displayName.toLowerCase() ||
          kLower.includes(shortName.toLowerCase()) ||
          (rawId.includes('flash') && kLower.includes('flash')) ||
          (rawId.includes('pro') && kLower.includes('pro')) ||
          (rawId.includes('3b') && kLower.includes('3b')) ||
          (rawId.includes('8b') && kLower.includes('8b'))
        ) {
          score = typeof val === 'number' ? val : parseFloat(String(val));
          break;
        }
      }
    }

    if (score === undefined || isNaN(score)) {
      score = meta.baselineConfidence;
    }

    const isWinner =
      rawId.toLowerCase() === winningRaw.toLowerCase() ||
      displayName.toLowerCase() === winningModelDisplayName.toLowerCase() ||
      (task.selected_model_or_tool &&
        (task.selected_model_or_tool.toLowerCase().includes(rawId.toLowerCase()) ||
          task.selected_model_or_tool.toLowerCase().includes(displayName.toLowerCase())));

    return {
      candidate: {
        id: rawId,
        aliases: [displayName, shortName],
        name: displayName,
        shortName: shortName,
        tier: meta.tier,
        tierCategory: meta.tierCategory,
        costUsd: meta.costUsd,
        latencyMs: meta.latencyMs,
        baselineConfidence: meta.baselineConfidence,
      },
      score,
      isWinner,
    };
  });

  // Calculate cost saved vs. Always-Frontier (Nova Lite = $0.00180)
  const selectedCost =
    task.estimated_cost !== undefined && task.estimated_cost > 0
      ? task.estimated_cost
      : winningCandidateMeta.costUsd;
  const costSaved = Math.max(0, FRONTIER_MODEL_COST - selectedCost);
  const percentSaved = Math.round((costSaved / FRONTIER_MODEL_COST) * 100);

  // Extract raw feature values used by the confidence predictor
  const rawFeatures = extractRawFeatures(task);

  const displayReason = (
    task.reason_for_selection ||
    `Selected ${winningModelDisplayName}: predicted confidence clears threshold ${threshold.toFixed(
      2
    )} at minimum operational cost.`
  );

  return (
    <div
      className="overflow-hidden rounded-2xl border border-primary/30 bg-card/95 p-4 shadow-md md:p-5"
      data-testid="router-decision-card"
    >
      {/* Header Banner */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border/80 pb-3.5">
        <div className="flex items-center gap-2.5">
          <div className="grid size-8 place-items-center rounded-lg bg-primary/10 text-primary">
            <Zap size={17} className="fill-primary" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="mono text-[10px] font-bold uppercase tracking-[.14em] text-primary">
                Core Innovation · Phase 7
              </span>
              <span className="rounded bg-primary/10 px-1.5 py-0.5 font-mono text-[9px] font-bold text-primary">
                PRE-EXECUTION
              </span>
            </div>
            <h3 className="text-[14px] font-extrabold tracking-tight text-foreground">
              Router Decision Card
            </h3>
          </div>
        </div>

        {/* Threshold Indicator Badge */}
        <div className="flex items-center gap-1.5 rounded-full border border-amber-500/30 bg-amber-500/10 px-2.5 py-1 text-[10.5px] font-semibold text-amber-700 dark:text-amber-400">
          <Scale size={13} />
          <span>Cutoff Threshold: <strong className="font-mono">{threshold.toFixed(2)}</strong></span>
        </div>
      </div>

      {/* 1. Winning Model Badge */}
      <div className="mt-4 rounded-xl border border-primary/30 bg-primary/[.05] p-3.5 shadow-xs">
        <div className="flex flex-col gap-2.5 sm:flex-row sm:items-start sm:justify-between">
          <div className="flex items-start gap-3">
            <div className="mt-0.5 grid size-7 shrink-0 place-items-center rounded-lg bg-primary text-primary-foreground shadow-xs">
              <Trophy size={14} className="text-amber-300" />
            </div>
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">
                  Winning Model
                </span>
                <span className="rounded-md bg-primary/15 px-2 py-0.5 font-mono text-[12px] font-bold text-primary">
                  {winningModelDisplayName}
                </span>
                <span className="rounded-md bg-secondary px-2 py-0.5 text-[10px] font-medium text-secondary-foreground">
                  {winningCandidateMeta.tierCategory === 'cheap_open' ? 'AWS Bedrock (Local)' : 'External Escalation'}
                </span>
              </div>
              <p className="mt-1.5 text-[12px] leading-relaxed text-foreground/90 font-medium">
                {displayReason}
              </p>
            </div>
          </div>

          <div className="flex shrink-0 items-center gap-1.5 rounded-lg border border-primary/20 bg-background/80 px-2.5 py-1.5 font-mono text-[11px] self-start">
            <span className="text-muted-foreground">Est. Cost:</span>
            <strong className="text-foreground">${selectedCost.toFixed(5)}</strong>
          </div>
        </div>
      </div>

      {/* 2. Cost Saved vs. Always-Frontier Banner */}
      <div className="mt-3 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-emerald-500/30 bg-emerald-500/[.07] px-4 py-2.5">
        <div className="flex items-center gap-2 text-[12px] font-bold text-emerald-800 dark:text-emerald-300">
          <span className="text-sm">💰</span>
          <span>
            Saved <strong className="font-mono text-[13px]">${costSaved.toFixed(5)}</strong> by routing to{' '}
            {winningModelShortName}
          </span>
        </div>
        <div className="flex items-center gap-2 font-mono text-[10.5px]">
          <span className="rounded-full bg-emerald-600/15 px-2.5 py-0.5 font-bold text-emerald-700 dark:text-emerald-300">
            {percentSaved > 0 ? `${percentSaved}% cheaper` : 'Frontier required'} vs. Frontier ($0.0070)
          </span>
        </div>
      </div>

      {/* 3. Candidates Considered with Threshold Indicator */}
      <div className="mt-4">
        <div className="mb-2 flex items-center justify-between">
          <span className="mono text-[10px] font-bold uppercase tracking-[.1em] text-muted-foreground">
            Candidates Evaluated & Predicted Confidence
          </span>
          <div className="flex items-center gap-3 text-[10px] text-muted-foreground">
            <span className="flex items-center gap-1">
              <span className="size-2 rounded-full bg-emerald-500" /> ≥0.85 (Pass)
            </span>
            <span className="flex items-center gap-1">
              <span className="size-2 rounded-full bg-amber-500" /> 0.70–0.84
            </span>
            <span className="flex items-center gap-1">
              <span className="size-2 rounded-full bg-rose-500" /> &lt;0.70
            </span>
          </div>
        </div>

        <div className="space-y-2.5">
          {candidateScores.map(({ candidate, score, isWinner }) => {
            const pct = Math.round(score * 100);
            const clearsThreshold = score >= threshold;
            const barColor =
              score >= 0.85
                ? 'bg-emerald-500'
                : score >= 0.70
                ? 'bg-amber-500'
                : 'bg-rose-500';
            const badgeBg =
              score >= 0.85
                ? 'text-emerald-700 bg-emerald-500/15 border-emerald-500/30'
                : score >= 0.70
                ? 'text-amber-700 bg-amber-500/15 border-amber-500/30'
                : 'text-rose-700 bg-rose-500/15 border-rose-500/30';

            return (
              <div
                key={candidate.id}
                className={`group rounded-xl border p-2.5 transition-all ${
                  isWinner
                    ? 'border-primary/40 bg-primary/[.04] shadow-xs'
                    : 'border-border/70 bg-card/60'
                }`}
              >
                <div className="flex items-center justify-between gap-2 text-[11.5px]">
                  <div className="flex items-center gap-2 min-w-0">
                    {isWinner ? (
                      <span className="grid size-4 place-items-center rounded-full bg-primary text-primary-foreground">
                        <CheckCircle2 size={12} strokeWidth={3} />
                      </span>
                    ) : (
                      <span className="size-1.5 rounded-full bg-muted-foreground/40 ml-1 mr-1.5" />
                    )}
                    <span className={`font-semibold truncate ${isWinner ? 'text-primary' : 'text-foreground'}`}>
                      {candidate.name}
                    </span>
                    <span className="hidden sm:inline font-mono text-[9.5px] text-muted-foreground">
                      (${candidate.costUsd.toFixed(5)} · {candidate.latencyMs}ms)
                    </span>
                  </div>

                  <div className="flex items-center gap-2 shrink-0">
                    {isWinner && (
                      <span className="rounded bg-primary text-primary-foreground px-1.5 py-0.5 font-mono text-[9px] font-bold uppercase tracking-wider">
                        WINNER
                      </span>
                    )}
                    <span
                      className={`mono rounded-md border px-1.5 py-0.5 text-[11px] font-bold ${badgeBg}`}
                    >
                      {pct}%
                    </span>
                  </div>
                </div>

                {/* Bar with 0.85 Threshold Dashed Line */}
                <div className="relative mt-2 h-2.5 w-full overflow-hidden rounded-full bg-secondary/80">
                  {/* Dashed Threshold Indicator (85%) */}
                  <div
                    className="absolute top-0 bottom-0 z-20 border-r-2 border-dashed border-amber-500"
                    style={{ left: `${threshold * 100}%` }}
                    title={`Decision Threshold: ${threshold.toFixed(2)}`}
                  />

                  {/* Confidence Fill Bar */}
                  <div
                    className={`h-full rounded-full transition-all duration-500 ${barColor}`}
                    style={{ width: `${Math.min(100, Math.max(4, pct))}%` }}
                  />
                </div>
              </div>
            );
          })}
        </div>

        {/* Global threshold visual legend */}
        <div className="relative mt-1.5 flex items-center justify-between text-[9.5px] text-muted-foreground px-1 font-mono">
          <span>0.00</span>
          <span
            className="absolute -translate-x-1/2 font-bold text-amber-600 dark:text-amber-400"
            style={{ left: `${threshold * 100}%` }}
          >
            ▲ 0.85 Threshold
          </span>
          <span>1.00</span>
        </div>
      </div>

      {/* 4. Feature Inputs Expandable Section */}
      <div className="mt-4 border-t border-border/80 pt-3">
        <button
          onClick={() => setShowFeatures(!showFeatures)}
          className="focus-ring flex w-full items-center justify-between rounded-lg px-2 py-1.5 text-left text-[11.5px] font-bold text-muted-foreground hover:bg-secondary/60 hover:text-foreground transition-colors"
          data-testid="button-toggle-router-features"
        >
          <div className="flex items-center gap-2">
            <Sliders size={13} className="text-primary" />
            <span>Deterministic Feature Inputs ({Object.keys(rawFeatures).length} signals evaluated)</span>
          </div>
          <ChevronDown
            size={14}
            className={`transition-transform duration-200 ${showFeatures ? 'rotate-180' : ''}`}
          />
        </button>

        {showFeatures && (
          <div className="mt-2.5 grid gap-2.5 sm:grid-cols-2 rounded-xl bg-secondary/40 p-3 text-[11px] border border-border/60">
            {/* Complexity Score */}
            <div className="rounded-lg bg-card p-2.5 border border-border/50">
              <div className="flex items-center justify-between">
                <span className="font-semibold text-foreground">query_complexity</span>
                <span className="mono font-bold text-primary">
                  {rawFeatures.complexity_score !== undefined
                    ? Number(rawFeatures.complexity_score).toFixed(4)
                    : '0.2850'}
                </span>
              </div>
              <p className="mt-1 text-[10px] text-muted-foreground">
                Evaluates prompt length, multi-step triggers, and domain vocabulary
              </p>
            </div>

            {/* Data Completeness */}
            <div className="rounded-lg bg-card p-2.5 border border-border/50">
              <div className="flex items-center justify-between">
                <span className="font-semibold text-foreground">data_completeness</span>
                <span className="mono font-bold text-primary">
                  {rawFeatures.data_completeness !== undefined
                    ? Number(rawFeatures.data_completeness).toFixed(4)
                    : '0.7500'}
                </span>
              </div>
              <p className="mt-1 text-[10px] text-muted-foreground">
                Presence of survey number (+0.40) & admin village context (+0.35)
              </p>
            </div>

            {/* Image Quality Score */}
            <div className="rounded-lg bg-card p-2.5 border border-border/50">
              <div className="flex items-center justify-between">
                <span className="font-semibold text-foreground">image_quality_score</span>
                <span className="mono font-bold text-primary">
                  {rawFeatures.image_quality_score !== null &&
                  rawFeatures.image_quality_score !== undefined
                    ? Number(rawFeatures.image_quality_score).toFixed(4)
                    : 'N/A (Text-only)'}
                </span>
              </div>
              <p className="mt-1 text-[10px] text-muted-foreground">
                Heuristic resolution & file integrity for multimodal classification
              </p>
            </div>

            {/* Domain Match / Similarity */}
            <div className="rounded-lg bg-card p-2.5 border border-border/50">
              <div className="flex items-center justify-between">
                <span className="font-semibold text-foreground">domain_match</span>
                <span className="mono font-bold text-primary">
                  {rawFeatures.domain_match !== undefined
                    ? Number(rawFeatures.domain_match).toFixed(4)
                    : '0.4500'}
                </span>
              </div>
              <p className="mt-1 text-[10px] text-muted-foreground">
                Jaccard similarity to calibrated agricultural & cadastral templates
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

/**
 * Extracts normalized raw feature values from task records with safe fallbacks.
 */
function extractRawFeatures(task: TaskRecord): {
  complexity_score?: number;
  data_completeness?: number;
  image_quality_score?: number | null;
  domain_match?: number;
} {
  // 1. Check direct task.features
  const feats = (task as any).features;
  if (feats && typeof feats === 'object') {
    return {
      complexity_score: feats.query_complexity ?? feats.complexity_score,
      data_completeness: feats.data_completeness,
      image_quality_score: feats.image_quality ?? feats.image_quality_score ?? null,
      domain_match: feats.similarity_to_past_queries ?? feats.domain_match,
    };
  }

  // 2. Check if actual_result contains features
  if (task.actual_result && typeof task.actual_result === 'object') {
    const resFeats = (task.actual_result as any).features;
    if (resFeats && typeof resFeats === 'object') {
      return {
        complexity_score: resFeats.query_complexity ?? resFeats.complexity_score,
        data_completeness: resFeats.data_completeness,
        image_quality_score: resFeats.image_quality ?? resFeats.image_quality_score ?? null,
        domain_match: resFeats.similarity_to_past_queries ?? resFeats.domain_match,
      };
    }
  }

  // 3. Check if actual_result is JSON string
  if (typeof task.actual_result === 'string') {
    try {
      const parsed = JSON.parse(task.actual_result);
      if (parsed?.features) {
        return {
          complexity_score: parsed.features.query_complexity,
          data_completeness: parsed.features.data_completeness,
          image_quality_score: parsed.features.image_quality ?? null,
          domain_match: parsed.features.similarity_to_past_queries,
        };
      }
    } catch {
      // String wasn't JSON, continue to inference
    }
  }

  // 4. Default calibrated signal values based on task context
  const desc = (task.description + ' ' + (task.reason_for_selection || '')).toLowerCase();
  const complexityMatch = desc.match(/complexity\s*\(([0-9.]+)\)/i);
  const complexity = complexityMatch ? parseFloat(complexityMatch[1]) : 0.285;

  return {
    complexity_score: complexity,
    data_completeness: 0.75,
    image_quality_score: desc.includes('photo') || desc.includes('image') ? 0.80 : null,
    domain_match: 0.45,
  };
}
