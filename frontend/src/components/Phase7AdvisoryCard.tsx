/**
 * Phase7AdvisoryCard.tsx
 *
 * Medium-sized, calm, professional advisory component for Cropsy.
 * Implements a restrained dark palette from the app theme tokens (card, border, success, warning, destructive),
 * 15px-16px readable text, compact badges, and clean information hierarchy.
 */

import React, { type ReactNode, useState } from "react";
import ReactMarkdown from "react-markdown";
import { ParcelFactsCard } from "./ParcelFactsCard";
import { FertilizerGuides } from "./FertilizerGuides";
import { VisualReport } from "./VisualReport";
import { CrossCheck, ComparePlain } from "./CompareAndCheck";
import { isDebugView } from "@/lib/debugView";
import { AnswerMedia } from "./AnswerMedia";
import { consentHeader } from "@/lib/privacy";
import { DoseHelper } from "./DoseHelper";
import { getApiSettings } from "@/lib/cropsy-api";
import remarkGfm from "remark-gfm";
import {
  AlertTriangle,
  BookOpen,
  CheckCircle,
  ChevronDown,
  ChevronUp,
  Clock,
  FlaskConical,
  ShieldAlert,
  ShieldCheck,
  Search,
  XCircle,
  Zap,
  ThumbsUp,
  ThumbsDown,
} from "lucide-react";

import type {
  Phase7AdvisoryResult,
  Phase7Source,
  Phase7Verification,
} from "@/lib/cropsy-api";

// ─── Evidence provenance badge ────────────────────────────────────────────────
type ProvenanceLabel =
  | "authoritative"
  | "derived"
  | "representative"
  | "ai_synthesis"
  | "observed"
  | "not_available"
  | string;

const PROVENANCE_STYLES: Record<
  string,
  { bg: string; color: string; border: string; label: string }
> = {
  authoritative: {
    bg: "color-mix(in oklab, var(--success) 12%, transparent)",
    color: "var(--success)",
    border: "color-mix(in oklab, var(--success) 28%, transparent)",
    label: "AUTHORITATIVE",
  },
  derived: {
    bg: "color-mix(in oklab, var(--muted-foreground) 12%, transparent)",
    color: "var(--muted-foreground)",
    border: "color-mix(in oklab, var(--muted-foreground) 24%, transparent)",
    label: "DERIVED",
  },
  representative: {
    bg: "color-mix(in oklab, var(--warning) 12%, transparent)",
    color: "var(--warning)",
    border: "color-mix(in oklab, var(--warning) 28%, transparent)",
    label: "REPRESENTATIVE",
  },
  ai_synthesis: {
    bg: "color-mix(in oklab, var(--muted-foreground) 10%, transparent)",
    color: "color-mix(in oklab, var(--muted-foreground) 70%, transparent)",
    border: "color-mix(in oklab, var(--muted-foreground) 20%, transparent)",
    label: "AI SYNTHESIS",
  },
  observed: {
    bg: "color-mix(in oklab, var(--success) 12%, transparent)",
    color: "var(--success)",
    border: "color-mix(in oklab, var(--success) 28%, transparent)",
    label: "OBSERVED",
  },
  not_available: {
    bg: "color-mix(in oklab, var(--muted-foreground) 8%, transparent)",
    color: "color-mix(in oklab, var(--muted-foreground) 70%, transparent)",
    border: "color-mix(in oklab, var(--muted-foreground) 18%, transparent)",
    label: "NOT AVAILABLE",
  },
};

function ProvenanceBadge({ provenance }: { provenance: ProvenanceLabel }) {
  const style = PROVENANCE_STYLES[provenance] ?? {
    bg: "color-mix(in oklab, var(--muted-foreground) 10%, transparent)",
    color: "color-mix(in oklab, var(--muted-foreground) 70%, transparent)",
    border: "color-mix(in oklab, var(--muted-foreground) 20%, transparent)",
    label: provenance.toUpperCase().replace(/_/g, " "),
  };
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        padding: "3px 7px",
        borderRadius: "6px",
        background: style.bg,
        color: style.color,
        border: `1px solid ${style.border}`,
        fontSize: "11px",
        fontFamily: "'JetBrains Mono', 'Fira Code', 'DM Mono', monospace",
        fontWeight: 600,
        letterSpacing: "0.03em",
      }}
    >
      {style.label}
    </span>
  );
}

// ─── Verification status badge ────────────────────────────────────────────────
function VerificationBadge({ verification }: { verification?: Phase7Verification }) {
  if (!verification) return null;
  const pass = verification.success;
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 5,
        padding: "3px 8px",
        borderRadius: "6px",
        background: pass ? "color-mix(in oklab, var(--success) 12%, transparent)" : "color-mix(in oklab, var(--destructive) 12%, transparent)",
        color: pass ? "var(--success)" : "var(--destructive)",
        border: `1px solid ${pass ? "color-mix(in oklab, var(--success) 28%, transparent)" : "color-mix(in oklab, var(--destructive) 28%, transparent)"}`,
        fontSize: "11.5px",
        fontFamily: "'JetBrains Mono', 'Fira Code', 'DM Mono', monospace",
        fontWeight: 600,
        letterSpacing: "0.02em",
      }}
    >
      {pass ? <ShieldCheck size={12} /> : <ShieldAlert size={12} />}
      {pass
        ? `VERIFIED ${verification.checks_passed}/${verification.total_checks}`
        : `FLAGGED ${verification.flags?.length ?? 0} issue(s)`}
    </span>
  );
}

// ─── Section wrapper ──────────────────────────────────────────────────────────
function Section({
  title,
  icon,
  variant = "default",
  children,
}: {
  title: string;
  icon?: ReactNode;
  variant?: "default" | "recommendation" | "risk" | "action";
  children: ReactNode;
}) {
  let borderColor = "var(--border)";
  let bg = "color-mix(in oklab, var(--card) 35%, transparent)";
  let titleColor = "var(--muted-foreground)";

  if (variant === "recommendation") {
    borderColor = "color-mix(in oklab, var(--success) 30%, transparent)";
    bg = "color-mix(in oklab, var(--success) 5%, transparent)";
    titleColor = "var(--success)";
  } else if (variant === "risk") {
    borderColor = "color-mix(in oklab, var(--warning) 30%, transparent)";
    bg = "color-mix(in oklab, var(--warning) 5%, transparent)";
    titleColor = "var(--warning)";
  } else if (variant === "action") {
    borderColor = "var(--border)";
    bg = "color-mix(in oklab, var(--card) 45%, transparent)";
    titleColor = "var(--muted-foreground)";
  }

  return (
    <div
      style={{
        marginTop: 12,
        padding: "12px 14px",
        border: `1px solid ${borderColor}`,
        borderRadius: 10,
        background: bg,
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 6,
          marginBottom: 8,
          color: titleColor,
          fontFamily: "'JetBrains Mono', 'Fira Code', 'DM Mono', monospace",
          fontSize: "12px",
          fontWeight: 600,
          letterSpacing: "0.05em",
        }}
      >
        {icon && (
          <span style={{ display: "flex", alignItems: "center" }}>{icon}</span>
        )}
        {title}
      </div>
      {children}
    </div>
  );
}

// ─── Bullet list ──────────────────────────────────────────────────────────────
function BulletList({ items }: { items: string[] }) {
  if (!items || items.length === 0) return null;
  return (
    <ul
      style={{
        margin: 0,
        paddingLeft: 18,
        listStyle: "disc",
        color: "var(--foreground)",
        fontSize: "15px",
        lineHeight: 1.55,
        fontWeight: 400,
      }}
    >
      {items.map((item, i) => (
        <li key={i} style={{ marginBottom: 5 }}>
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
              p: ({ children }) => <span>{children}</span>,
              strong: ({ children }) => <strong style={{ fontWeight: 600, color: "var(--success)" }}>{children}</strong>,
            }}
          >
            {item}
          </ReactMarkdown>
        </li>
      ))}
    </ul>
  );
}

// ─── Source citation ──────────────────────────────────────────────────────────
function SourceTag({ source }: { source: Phase7Source }) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "flex-start",
        gap: 8,
        padding: "7px 10px",
        borderRadius: 6,
        background: "color-mix(in oklab, var(--card) 40%, transparent)",
        border: "1px solid var(--border)",
        marginBottom: 5,
      }}
    >
      <BookOpen
        size={13}
        style={{ color: "var(--success)", flexShrink: 0, marginTop: 3 }}
      />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div
          style={{
            fontSize: "13px",
            color: "var(--foreground)",
            fontWeight: 500,
            lineHeight: 1.4,
          }}
        >
          {source.title}
        </div>
        <div
          style={{
            display: "flex",
            gap: 7,
            alignItems: "center",
            marginTop: 3,
            flexWrap: "wrap",
          }}
        >
          {source.page && (
            <span
              style={{
                fontSize: "11px",
                fontFamily: "monospace",
                color: "color-mix(in oklab, var(--muted-foreground) 70%, transparent)",
              }}
            >
              {source.page}
            </span>
          )}
          {source.domain && (
            <span
              style={{
                fontSize: "11px",
                fontFamily: "monospace",
                color: "var(--muted-foreground)",
                background: "rgba(40, 64, 71, 0.6)",
                padding: "2px 5px",
                borderRadius: 4,
              }}
            >
              {source.domain.replace(/_/g, " ")}
            </span>
          )}
          {source.provenance && (
            <ProvenanceBadge provenance={source.provenance} />
          )}
        </div>
      </div>
    </div>
  );
}

// ─── Why This Matters Collapsible Component ──────────────────────────────────
function WhyThisMattersSection({
  items,
}: {
  items: Array<{
    parcel_fact: string;
    mechanism: string;
    claim?: string;
    source?: string;
    source_citation?: string;
    institution?: string;
    verified_status?: string;
  }>;
}) {
  const [isOpen, setIsOpen] = useState(false);

  if (!items || items.length === 0) return null;

  return (
    <div
      style={{
        marginTop: 10,
        border: "1px solid var(--border)",
        borderRadius: 8,
        background: "rgba(16, 33, 39, 0.5)",
        overflow: "hidden",
      }}
    >
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        style={{
          width: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "8px 12px",
          background: "transparent",
          border: "none",
          cursor: "pointer",
          fontSize: "12px",
          fontFamily: "'JetBrains Mono', 'Fira Code', 'DM Mono', monospace",
          fontWeight: 600,
          color: "var(--success)",
          letterSpacing: "0.03em",
        }}
      >
        <span style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <FlaskConical size={13} style={{ color: "var(--success)" }} />
          WHY THIS MATTERS (BIOLOGICAL & CHEMICAL GROUNDING)
        </span>
        {isOpen ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
      </button>

      {isOpen && (
        <div
          style={{
            padding: "10px 12px",
            borderTop: "1px solid var(--border)",
            background: "rgba(11, 23, 27, 0.7)",
          }}
        >
          {items.map((item, idx) => {
            const isVerified = item.verified_status !== "NOT_AVAILABLE_IN_KB";
            const citation = item.source || item.source_citation;
            return (
              <div
                key={idx}
                style={{
                  marginBottom: idx < items.length - 1 ? 10 : 0,
                  paddingBottom: idx < items.length - 1 ? 10 : 0,
                  borderBottom:
                    idx < items.length - 1
                      ? "1px dashed var(--border)"
                      : "none",
                }}
              >
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    gap: 8,
                    marginBottom: 4,
                    flexWrap: "wrap",
                  }}
                >
                  <span
                    style={{
                      fontSize: "12.5px",
                      fontWeight: 600,
                      color: "var(--foreground)",
                    }}
                  >
                    PARCEL FACT: {item.parcel_fact}
                  </span>
                  <span
                    style={{
                      fontSize: "10.5px",
                      fontFamily: "monospace",
                      fontWeight: 600,
                      padding: "2px 6px",
                      borderRadius: 4,
                      background: isVerified
                        ? "color-mix(in oklab, var(--success) 12%, transparent)"
                        : "color-mix(in oklab, var(--destructive) 12%, transparent)",
                      color: isVerified ? "var(--success)" : "var(--destructive)",
                      border: `1px solid ${
                        isVerified
                          ? "color-mix(in oklab, var(--success) 28%, transparent)"
                          : "color-mix(in oklab, var(--destructive) 28%, transparent)"
                      }`,
                    }}
                  >
                    {isVerified ? "VERIFIED SCIENCE" : "NOT AVAILABLE IN KB"}
                  </span>
                </div>

                <div
                  style={{
                    fontSize: "14px",
                    color: "var(--muted-foreground)",
                    lineHeight: 1.55,
                    marginBottom: 4,
                    fontWeight: 400,
                  }}
                >
                  <strong style={{ color: "var(--foreground)", fontWeight: 500 }}>Mechanism:</strong>{" "}
                  {item.mechanism}
                </div>

                {citation && (
                  <div
                    style={{
                      fontSize: "11.5px",
                      color: "color-mix(in oklab, var(--muted-foreground) 70%, transparent)",
                      fontFamily:
                        "'JetBrains Mono', 'Fira Code', 'DM Mono', monospace",
                    }}
                  >
                    📚 Source: {citation}{" "}
                    {item.institution ? `[${item.institution}]` : ""}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ─── Main Component ───────────────────────────────────────────────────────────
export function Phase7AdvisoryCard({
  result,
  parcelId,
  onSelectParcel,
  onAskFollowUp,
}: {
  result: Phase7AdvisoryResult;
  parcelId?: string | null;
  onSelectParcel?: (id: string) => void;
  onAskFollowUp?: (q: string) => void;
}) {
  const { answer, actions, data_quality, model, verification } = result;
  // the server sends null (not undefined) for lists it has nothing for
  const recommendations = result.recommendations ?? [];
  const reasons = result.reasons ?? [];
  const risks = result.risks ?? [];
  const sources = result.sources ?? [];
  // 'Be careful' lines are model-written: only safety-type cautions are shown (a general 'may affect yield' remark is not backed by the guide)
  const safeRisks = (result.risks ?? []).filter((r) => /toxic|poison|protective|banned|restricted|label|do not|never|avoid|harm|children|pregnan|burn|flammable|wear/i.test(r));
  const limitations = result.limitations ?? [];

  const effectiveParcelId = result.parcel_id || parcelId || null;
  const completeness =
    typeof data_quality === "object" && data_quality !== null
      ? data_quality.completeness_score
      : undefined;
  const [showDevInfo, setShowDevInfo] = React.useState<boolean>(false);
  const debugView = React.useMemo(() => isDebugView(), []);
  const needsOfficer = result.confidence?.level === "low" && !limitations.some((l) => /general guidance, not a TNAU|not sourced from the knowledge base/i.test(l));
  const isGeneral = limitations.some((l) => /general guidance, not a TNAU|not sourced from the knowledge base/i.test(l));
  const essentialRx = /banned|restricted|poison|toxic|not recommended|set your region|is general guidance only|farm elsewhere|could not be double-checked|not provided|will not guess/i;
  // One short note list: the general-guidance line is already the amber badge, and repeats are dropped
  const notes = React.useMemo(() => {
    const seen = new Set<string>();
    return limitations.filter((l) => {
      const k = l.trim().toLowerCase();
      if (!k || seen.has(k) || (isGeneral && /general guidance, not a TNAU|not sourced from the knowledge base/i.test(l))) return false;
      seen.add(k);
      return true;
    });
  }, [limitations, isGeneral]);
  const shownNotes = debugView ? notes : notes.filter((n) => essentialRx.test(n)).slice(0, 2);

  // Clean legacy dashboard/demo headers from synthesized responses
  const cleanedAnswer = React.useMemo(() => {
    if (!answer) return "";
    let t = answer;
    // Strip "Advisory for General Query (…):\n" or "Advisory for TM-01 (…):\n"
    t = t.replace(/^#*\s*Advisory\s+for\s+[^\n]+\n*/im, "");
    // Strip "- Verdict / Recommendation:" prefix line
    t = t.replace(/^[-*#\s]*Verdict\s*\/\s*Recommendation[:\s]*/im, "");
    // Strip "- Primary Agronomic Rationale:" prefix line
    t = t.replace(/^[-*#\s]*Primary Agronomic Rationale[:\s]*/im, "");
    // Strip "- Key Risk:" prefix line
    t = t.replace(/^[-*#\s]*Key Risk[:\s]*/im, "");
    // Strip leading label lines like "General Agriculture:" or "Irrigation Management:"
    t = t.replace(/^[A-Z][A-Za-z ]+:\s*\n/m, "");
    return t.trim();
  }, [answer]);


  // Deduplicate sources and limit to top 3 most relevant documents
  const compactSources = React.useMemo(() => {
    const seenTitles = new Set<string>();
    const unique: Phase7Source[] = [];
    for (const s of sources) {
      const cleanTitle = (s.title || "").trim();
      const normKey = cleanTitle.toLowerCase();
      if (!normKey || seenTitles.has(normKey)) continue;
      seenTitles.add(normKey);
      unique.push({
        ...s,
        title: cleanTitle,
        provenance: s.provenance || "authoritative",
      });
      if (unique.length >= 3) break;
    }
    return unique;
  }, [sources]);

  return (
    <div
      style={{
        fontSize: "15px",
        color: "var(--foreground)",
        lineHeight: 1.55,
      }}
    >
      {/* Normal view: no confidence badge. Only "general guidance" (so it is not mistaken for a TNAU recommendation) and a genuine "check with an officer" are shown; the debug toggle is development-only. */}
      {(isGeneral || needsOfficer || debugView) && (
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
          {isGeneral ? (
            <span title="Not from a TNAU document: general guidance." style={{ fontSize: "11px", padding: "2px 8px", borderRadius: 999, border: "1px solid color-mix(in oklab, var(--warning) 40%, transparent)", color: "var(--warning)" }}>
              General guidance
            </span>
          ) : needsOfficer ? (
            <span data-testid="confidence-badge" title={result.confidence?.why.join(" ")} style={{ fontSize: "11px", padding: "2px 8px", borderRadius: 999, border: "1px solid color-mix(in oklab, var(--destructive) 40%, transparent)", color: "var(--destructive)" }}>
              Check with an officer
            </span>
          ) : <span />}
          {debugView && (
            <button type="button" onClick={() => setShowDevInfo(!showDevInfo)} style={{ fontSize: "10px", fontFamily: "monospace", padding: "2px 6px", borderRadius: 4, background: showDevInfo ? "rgba(255, 255, 255, 0.12)" : "transparent", border: "1px solid rgba(255, 255, 255, 0.08)", color: "var(--muted-foreground)", cursor: "pointer" }}>
              {showDevInfo ? "Hide debug" : "Debug"}
            </button>
          )}
        </div>
      )}

      {result.cross_check && <CrossCheck cc={result.cross_check} />}

      {/* Dev / Admin Debug Collapsible Container */}
      {showDevInfo && (() => {
        const obs = result.observability || {};
        const route = obs.route || result.route || "PATH_A";
        const agentModel = obs.agent_model || result.agent_model || (route === "PATH_B" ? "Nova Micro" : null);
        const modelSelected = obs.model_selected || result.model_selected || model?.model_selected || model?.model_name || "NONE";
        const isVerified = obs.verified !== undefined ? obs.verified : (result.verified ?? verification?.success ?? true);
        const dataQualityVal = typeof obs.data_quality === "string"
          ? obs.data_quality
          : (typeof result.data_quality === "string"
              ? result.data_quality
              : (completeness != null ? `${Math.round(completeness * 100)}% verified` : "verified"));
        const estimatedCostUsd = obs.estimated_cost_usd ?? result.estimated_cost_usd ?? model?.estimated_cost_usd ?? 0.0;
        const toolsCalled = obs.tools_called || result.tools_called || (route === "PATH_A" ? ["deterministic_tools"] : ["agentic_rag"]);
        const latencyMs = obs.latency_ms ?? model?.latency_ms ?? 0;

        return (
          <div
            data-testid="admin-debug-panel"
            style={{
              padding: "10px 12px",
              borderRadius: 8,
              background: "rgba(11, 23, 27, 0.9)",
              border: "1px solid var(--success)",
              marginBottom: 12,
              fontSize: "11px",
              fontFamily: "'JetBrains Mono', 'Fira Code', 'DM Mono', monospace",
              color: "var(--muted-foreground)",
              boxShadow: "0 4px 12px rgba(0,0,0,0.4)",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6, borderBottom: "1px solid rgba(255,255,255,0.08)", paddingBottom: 4 }}>
              <span style={{ fontWeight: 700, color: "var(--success)", letterSpacing: "0.05em" }}>
                🛠️ OBSERVABILITY & ROUTER TRACE
              </span>
              <span style={{ fontSize: "10px", padding: "1px 5px", borderRadius: 3, background: route === "PATH_B" ? "rgba(249, 115, 22, 0.2)" : "color-mix(in oklab, var(--success) 20%, transparent)", color: route === "PATH_B" ? "#fb923c" : "var(--success)" }}>
                {route}
              </span>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "6px 12px" }}>
              <div>
                <span style={{ color: "color-mix(in oklab, var(--muted-foreground) 70%, transparent)" }}>Route:</span>{" "}
                <strong style={{ color: route === "PATH_B" ? "#fb923c" : "var(--success)" }}>{route}</strong>
              </div>
              <div>
                <span style={{ color: "color-mix(in oklab, var(--muted-foreground) 70%, transparent)" }}>Agent Model:</span>{" "}
                <strong style={{ color: "var(--foreground)" }}>{agentModel || "—"}</strong>
              </div>
              <div>
                <span style={{ color: "color-mix(in oklab, var(--muted-foreground) 70%, transparent)" }}>Model Selected:</span>{" "}
                <strong style={{ color: modelSelected === "NONE" ? "color-mix(in oklab, var(--muted-foreground) 70%, transparent)" : "var(--primary)" }}>{modelSelected}</strong>
              </div>
              <div>
                <span style={{ color: "color-mix(in oklab, var(--muted-foreground) 70%, transparent)" }}>19-Rule Verifier:</span>{" "}
                <strong style={{ color: isVerified ? "var(--success)" : "var(--destructive)" }}>
                  {isVerified ? "✅ VERIFIED (PASS)" : "⚠️ FLAGGED"}
                </strong>
              </div>
              <div>
                <span style={{ color: "color-mix(in oklab, var(--muted-foreground) 70%, transparent)" }}>Data Quality:</span>{" "}
                <strong style={{ color: "var(--foreground)" }}>{String(dataQualityVal)}</strong>
              </div>
              <div>
                <span style={{ color: "color-mix(in oklab, var(--muted-foreground) 70%, transparent)" }}>Estimated Cost:</span>{" "}
                <strong style={{ color: "#fb923c" }}>
                  ${Number(estimatedCostUsd).toFixed(5)} USD
                </strong>
              </div>
              <div>
                <span style={{ color: "color-mix(in oklab, var(--muted-foreground) 70%, transparent)" }}>Latency:</span>{" "}
                <strong style={{ color: "var(--foreground)" }}>{Math.round(latencyMs)}ms</strong>
              </div>
              <div>
                <span style={{ color: "color-mix(in oklab, var(--muted-foreground) 70%, transparent)" }}>Bedrock Invoked:</span>{" "}
                <strong style={{ color: model?.bedrock_invoked || obs.bedrock_invoked ? "var(--success)" : "color-mix(in oklab, var(--muted-foreground) 70%, transparent)" }}>
                  {model?.bedrock_invoked || obs.bedrock_invoked ? "YES" : "NO"}
                </strong>
              </div>
              {obs.vision_model && (
                <div>
                  <span style={{ color: "color-mix(in oklab, var(--muted-foreground) 70%, transparent)" }}>Vision Model:</span>{" "}
                  <strong style={{ color: "#fb923c" }}>{obs.vision_model}</strong>
                </div>
              )}
              {obs.titan_text_v2_invoked && (
                <div>
                  <span style={{ color: "color-mix(in oklab, var(--muted-foreground) 70%, transparent)" }}>Text RAG:</span>{" "}
                  <strong style={{ color: "var(--success)" }}>Titan Text V2 ({obs.titan_text_chunks_retrieved} chunks)</strong>
                </div>
              )}
              {obs.titan_multimodal_invoked && (
                <div>
                  <span style={{ color: "color-mix(in oklab, var(--muted-foreground) 70%, transparent)" }}>Visual RAG:</span>{" "}
                  <strong style={{ color: "var(--success)" }}>Titan Multimodal ({obs.titan_multimodal_matches} matches)</strong>
                </div>
              )}
              {obs.evidence_gap_detected !== undefined && (
                <div>
                  <span style={{ color: "color-mix(in oklab, var(--muted-foreground) 70%, transparent)" }}>Evidence Gap:</span>{" "}
                  <strong style={{ color: obs.evidence_gap_detected ? "#fb923c" : "var(--success)" }}>
                    {obs.evidence_gap_detected ? "GAP DETECTED" : "LOCAL SUFFICIENT"}
                  </strong>
                </div>
              )}
              {obs.external_retrieval_attempted && (
                <div>
                  <span style={{ color: "color-mix(in oklab, var(--muted-foreground) 70%, transparent)" }}>External Retrieval:</span>{" "}
                  <strong style={{ color: "var(--primary)" }}>
                    {obs.external_sources_accepted || 0} accepted / {obs.external_sources_found || 0} found
                  </strong>
                </div>
              )}
            </div>

            {toolsCalled.length > 0 && (
              <div style={{ marginTop: 6, paddingTop: 4, borderTop: "1px dashed rgba(255,255,255,0.08)" }}>
                <span style={{ color: "color-mix(in oklab, var(--muted-foreground) 70%, transparent)" }}>Tools Called:</span>{" "}
                <span style={{ color: "var(--primary)" }}>{toolsCalled.join(", ")}</span>
              </div>
            )}
          </div>
        );
      })()}

      {/* Main answer text formatted with Markdown */}
      {cleanedAnswer && (
        <div
          className="advisory-markdown-content"
          style={{
            margin: "10px 0 14px",
            color: "var(--foreground)",
            fontSize: "15px",
            lineHeight: 1.6,
            fontWeight: 400,
          }}
        >
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
              h1: ({ children }) => <h1 style={{ fontSize: "17px", fontWeight: 700, color: "#FFFFFF", marginTop: "14px", marginBottom: "6px" }}>{children}</h1>,
              h2: ({ children }) => <h2 style={{ fontSize: "16px", fontWeight: 600, color: "var(--success)", marginTop: "12px", marginBottom: "6px" }}>{children}</h2>,
              h3: ({ children }) => <h3 style={{ fontSize: "15px", fontWeight: 600, color: "var(--primary)", marginTop: "10px", marginBottom: "4px" }}>{children}</h3>,
              h4: ({ children }) => <h4 style={{ fontSize: "14px", fontWeight: 600, color: "var(--muted-foreground)", marginTop: "8px", marginBottom: "4px" }}>{children}</h4>,
              p: ({ children }) => <p style={{ marginBottom: "10px", color: "var(--foreground)" }}>{children}</p>,
              strong: ({ children }) => <strong style={{ fontWeight: 600, color: "var(--success)" }}>{children}</strong>,
              ul: ({ children }) => <ul style={{ listStyleType: "disc", paddingLeft: "20px", marginBottom: "10px" }}>{children}</ul>,
              ol: ({ children }) => <ol style={{ listStyleType: "decimal", paddingLeft: "20px", marginBottom: "10px" }}>{children}</ol>,
              li: ({ children }) => <li style={{ marginBottom: "4px", color: "var(--foreground)" }}>{children}</li>,
              table: ({ children }) => (
                <div style={{ overflowX: "auto", margin: "12px 0" }}>
                  <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "13px", border: "1px solid var(--border)", background: "color-mix(in oklab, var(--card) 40%, transparent)" }}>
                    {children}
                  </table>
                </div>
              ),
              th: ({ children }) => <th style={{ border: "1px solid var(--border)", padding: "6px 10px", textAlign: "left", background: "color-mix(in oklab, var(--success) 10%, transparent)", color: "var(--success)", fontWeight: 600 }}>{children}</th>,
              td: ({ children }) => <td style={{ border: "1px solid var(--border)", padding: "6px 10px", color: "var(--foreground)" }}>{children}</td>,
            }}
          >
            {cleanedAnswer}
          </ReactMarkdown>
        </div>
      )}


      {/* What to do: the steps behind the headline answer (always shown, not only when the headline is missing) */}
      {recommendations.length > 0 && (
        <Section title="WHAT TO DO" variant="recommendation" icon={<CheckCircle size={13} style={{ color: "var(--success)" }} />}>
          <ol style={{ margin: 0, paddingLeft: 20, listStyle: "decimal", fontSize: "14.5px", lineHeight: 1.55 }}>
            {recommendations.map((r, i) => (
              <li key={i} style={{ marginBottom: 5 }}>
                <ReactMarkdown remarkPlugins={[remarkGfm]} components={{ p: ({ children }) => <span>{children}</span>, strong: ({ children }) => <strong style={{ fontWeight: 600, color: "var(--success)" }}>{children}</strong> }}>{r}</ReactMarkdown>
              </li>
            ))}
          </ol>
        </Section>
      )}
      {effectiveParcelId && actions && ((actions.immediate?.length ?? 0) + (actions.next_24_hours?.length ?? 0) + (actions.next_3_to_7_days?.length ?? 0) + (actions.watch_for?.length ?? 0)) > 0 && (
        <Section title="WHEN" variant="action" icon={<Zap size={13} style={{ color: "var(--success)" }} />}>
          {([["Now", actions.immediate], ["Next 24 hours", actions.next_24_hours], ["In 3 to 7 days", actions.next_3_to_7_days], ["Watch for", actions.watch_for]] as [string, string[] | undefined][])
            .filter(([, v]) => v && v.length > 0)
            .map(([label, v]) => (
              <div key={label} style={{ fontSize: "14px", marginBottom: 4 }}><strong style={{ color: "var(--muted-foreground)", fontWeight: 600 }}>{label}: </strong>{(v || []).join("; ")}</div>
            ))}
        </Section>
      )}
      {safeRisks.length > 0 && (
        <Section title="BE CAREFUL" variant="risk" icon={<AlertTriangle size={13} style={{ color: "var(--warning)" }} />}>
          <BulletList items={safeRisks} />
        </Section>
      )}

      {/* what the photo shows: kept under the answer, opened on request */}
      {result.visual_report && (
        <details className="mt-3 rounded-xl border border-border bg-card/40 p-3">
          <summary className="cursor-pointer select-none text-xs font-semibold">What the photo shows <span className="font-normal text-muted-foreground">(tap to see the description)</span></summary>
          <div className="mt-2"><VisualReport report={result.visual_report} /></div>
        </details>
      )}

      {result.parcel_facts && <ParcelFactsCard facts={result.parcel_facts} />}
      {result.fertilizer_guides && result.fertilizer_guides.length > 0 && <FertilizerGuides guides={result.fertilizer_guides} onAsk={onAskFollowUp} />}

      <AnswerMedia result={result} />

      {result.confidence?.label !== "Read from your document" && <DoseHelper text={`${cleanedAnswer} ${(recommendations || []).join(" ")}`} areaHa={(result.parcel_context as any)?.area_ha ?? null} />}

      {/* Visual observations — only shown for image queries when cleanedAnswer is absent */}
      {!cleanedAnswer && result.visual_observations && result.visual_observations.length > 0 && (
        <Section
          title="VISUAL OBSERVATIONS"
          icon={<Search size={13} style={{ color: "var(--primary)" }} />}
        >
          <BulletList items={result.visual_observations} />
        </Section>
      )}



      {/* Field Image Rendering if present */}
      {(result.image || result.parcel_context?.image) && (
        <div
          style={{
            margin: "12px 0 16px",
            padding: "10px",
            background: "color-mix(in oklab, var(--card) 50%, transparent)",
            border: "1px solid var(--border)",
            borderRadius: 8,
          }}
        >
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 6 }}>
            <span style={{ fontSize: "12px", fontWeight: 600, color: "var(--foreground)" }}>
              {result.image?.user_uploaded
                ? "📷 Field Photograph Analyzed"
                : result.image?.actual_parcel_photo
                  ? "📷 Verified Parcel Photograph"
                  : "🖼️ Field Reference Image"}
            </span>
            <span
              style={{
                fontSize: "11px",
                fontFamily: "'JetBrains Mono', 'Fira Code', 'DM Mono', monospace",
                padding: "2px 6px",
                borderRadius: 4,
                background: result.image?.user_uploaded || result.image?.actual_parcel_photo ? "color-mix(in oklab, var(--success) 15%, transparent)" : "color-mix(in oklab, var(--warning) 15%, transparent)",
                color: result.image?.user_uploaded || result.image?.actual_parcel_photo ? "var(--success)" : "var(--warning)",
                border: `1px solid ${result.image?.user_uploaded || result.image?.actual_parcel_photo ? "color-mix(in oklab, var(--success) 30%, transparent)" : "color-mix(in oklab, var(--warning) 30%, transparent)"}`,
              }}
            >
              {result.image?.user_uploaded ? "UPLOADED FIELD PHOTO" : result.image?.actual_parcel_photo ? "ACTUAL PARCEL PHOTO" : "REPRESENTATIVE REFERENCE"}
            </span>
          </div>
          {result.image?.image_path && !result.image?.user_uploaded && (
            <img
              src={`/api/v1/image?path=${encodeURIComponent(result.image.image_path)}`}
              alt="Field Reference"
              onError={(e) => {
                (e.target as HTMLElement).style.display = "none";
              }}
              style={{ width: "100%", maxHeight: 220, objectFit: "cover", borderRadius: 6, marginBottom: 6 }}
            />
          )}
          <div style={{ fontSize: "11.5px", color: "color-mix(in oklab, var(--muted-foreground) 70%, transparent)", fontStyle: "italic" }}>
            {result.image?.user_uploaded
              ? "Visual features and symptoms identified from uploaded farmer photograph."
              : result.image?.actual_parcel_photo
                ? "Verified on-site agricultural survey photograph."
                : "Representative field reference — not an actual parcel photograph."}
          </div>
        </div>
      )}

      {/* Fallback structured sections (rendered only when synthesized answer text is absent) */}
      {!cleanedAnswer && (
        <>
          {reasons.length > 0 && (
            <Section title="WHY THIS MATTERS">
              <BulletList items={reasons} />
            </Section>
          )}

        </>
      )}

      {/* Notes: only what a farmer needs for safety or place (banned or restricted chemical, other region); everything else is development-view only */}
      {shownNotes.length > 0 && (
        <p style={{ margin: "8px 0 2px", fontSize: "12px", color: "var(--muted-foreground)", lineHeight: 1.5 }}>{shownNotes.join(" ")}</p>
      )}

      {/* Sources & Evidence · Compact Collapsible */}
      {compactSources.length > 0 && (
        <details
          style={{
            margin: "6px 0 2px",
            background: "transparent",
            border: "none",
            borderRadius: 8,
            overflow: "hidden",
          }}
        >
          <summary
            style={{
              padding: "8px 12px",
              fontSize: "12px",
              fontWeight: 600,
              color: "var(--muted-foreground)",
              cursor: "pointer",
              userSelect: "none",
              display: "flex",
              alignItems: "center",
              gap: 6,
            }}
          >
            <BookOpen size={13} style={{ color: "var(--success)" }} />
            <span>Sources · {compactSources.length}</span>
          </summary>
          <div style={{ padding: "8px 12px 10px", display: "flex", flexDirection: "column", gap: 6, borderTop: "1px solid rgba(40, 64, 71, 0.4)" }}>
            {compactSources.map((src, i) => (
              <SourceTag key={i} source={src} />
            ))}
          </div>
        </details>
      )}

      {/* Data completeness (shown only in developer view) */}
      {showDevInfo && completeness != null && (
        <div
          style={{
            marginTop: 12,
            padding: "8px 10px",
            background: "color-mix(in oklab, var(--card) 30%, transparent)",
            border: "1px solid var(--border)",
            borderRadius: 8,
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 8,
              fontSize: "11.5px",
              fontFamily: "'JetBrains Mono', 'Fira Code', 'DM Mono', monospace",
              color: "color-mix(in oklab, var(--muted-foreground) 70%, transparent)",
            }}
          >
            <span style={{ fontWeight: 500, color: "var(--muted-foreground)" }}>
              Evidence completeness:
            </span>
            <div
              style={{
                flex: 1,
                height: 5,
                borderRadius: 3,
                background: "var(--card)",
                overflow: "hidden",
                maxWidth: 120,
              }}
            >
              <div
                style={{
                  height: "100%",
                  width: `${Math.round(completeness * 100)}%`,
                  background:
                    completeness > 0.7
                      ? "var(--success)"
                      : completeness > 0.4
                      ? "var(--warning)"
                      : "var(--destructive)",
                  borderRadius: 3,
                }}
              />
            </div>
            <span style={{ fontWeight: 600, color: "var(--foreground)" }}>
              {Math.round(completeness * 100)}%
            </span>
            {model?.latency_ms && (
              <span style={{ marginLeft: "auto" }}>
                {Math.round(model.latency_ms)}ms · {model.token_count ?? "?"}{" "}
                tokens
              </span>
            )}
          </div>
          <div
            style={{
              fontSize: "11px",
              color: "color-mix(in oklab, var(--muted-foreground) 70%, transparent)",
              marginTop: 3,
              fontFamily: "monospace",
            }}
          >
            Measures available physical & authoritative ground context — not
            model accuracy.
          </div>
        </div>
      )}

      {/* Verification flags */}
      {showDevInfo && verification && !verification.success && verification.flags.length > 0 && (
        <div
          style={{
            marginTop: 10,
            padding: "8px 12px",
            borderLeft: "3px solid var(--destructive)",
            borderRadius: "0 6px 6px 0",
            background: "color-mix(in oklab, var(--destructive) 10%, transparent)",
            color: "var(--destructive)",
            fontSize: "13px",
            lineHeight: 1.5,
          }}
        >
          <strong style={{ fontWeight: 600 }}>Verifier flags:</strong> {verification.flags.join(" · ")}
        </div>
      )}

      {/* Quick follow-up chips — parcel context only, conversational style */}
      {effectiveParcelId && onAskFollowUp && (
        <div style={{ marginTop: 10, display: "flex", gap: 5, flexWrap: "wrap" }}>
          <button
            type="button"
            onClick={() => onAskFollowUp(`What is the recommended irrigation schedule for ${effectiveParcelId} today?`)}
            style={{
              padding: "3px 8px",
              borderRadius: 12,
              fontSize: "10.5px",
              background: "color-mix(in oklab, var(--card) 60%, transparent)",
              border: "1px solid var(--border)",
              color: "var(--success)",
              cursor: "pointer",
            }}
          >
            💧 Irrigation schedule
          </button>
          <button
            type="button"
            onClick={() => onAskFollowUp(`Will upcoming rain affect operations on ${effectiveParcelId}?`)}
            style={{
              padding: "3px 8px",
              borderRadius: 12,
              fontSize: "10.5px",
              background: "color-mix(in oklab, var(--card) 60%, transparent)",
              border: "1px solid var(--border)",
              color: "color-mix(in oklab, var(--muted-foreground) 70%, transparent)",
              cursor: "pointer",
            }}
          >
            🌧️ Rain impact
          </button>
        </div>
      )}

      {debugView && !(result.fertilizer_guides && result.fertilizer_guides.length > 0 && result.route === "ROUTINE") && <ComparePlain result={result} />}

    </div>
  );
}


/** Two small icon buttons in the answer's action row: the farmer's thumbs up or down (saved on the server only if they agreed to help improve Cropsy). */
export function FeedbackButtons({ result }: { result: Phase7AdvisoryResult }) {
  const [feedback, setFeedbackState] = React.useState<"up" | "down" | null>(null);
  const send = (v: "up" | "down") => {
    setFeedbackState(v);
    void fetch(`${(getApiSettings().baseUrl || "").replace(/\/$/, "")}/api/feedback`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...consentHeader() },
      body: JSON.stringify({ query: result.query, parcel_id: result.parcel_id, route: result.route, helpful: v === "up", confidence: result.confidence?.level, answer: result.answer }),
    }).catch(() => undefined);
  };
  const cls = "rounded p-1.5 hover:bg-accent hover:text-foreground focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary";
  return (
    <>
      <button type="button" aria-label="Helpful" title="Helpful" className={cls} onClick={() => send("up")}><ThumbsUp className={`size-3.5 ${feedback === "up" ? "text-success" : ""}`} /></button>
      <button type="button" aria-label="Not helpful" title="Not helpful" className={cls} onClick={() => send("down")}><ThumbsDown className={`size-3.5 ${feedback === "down" ? "text-destructive" : ""}`} /></button>
    </>
  );
}
