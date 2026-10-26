import { useEffect, useMemo, useRef, useState } from "react";
import { useMediaQuery } from "@/lib/useMediaQuery";
import { ArrowLeft, Camera, Check, Clock, Copy, FileText, Leaf, Loader2, Map, Mic, Plus, RefreshCw, Sprout, Trash2, X } from "lucide-react";
import { useStickToBottomContext } from "use-stick-to-bottom";
import { Conversation, ConversationContent, ConversationScrollButton } from "@/components/ai-elements/conversation";
import { Message, MessageContent } from "@/components/ai-elements/message";
import {
  PromptInput,
  PromptInputButton,
  PromptInputFooter,
  PromptInputHeader,
  PromptInputSubmit,
  PromptInputTextarea,
  PromptInputTools,
} from "@/components/ai-elements/prompt-input";
import { Phase7AdvisoryCard, FeedbackButtons } from "@/components/Phase7AdvisoryCard";
import { Button } from "@/components/ui/button";
import { THEN_MALAI_PARCELS } from "@/lib/parcels";
import { FieldMap } from "./field-map";
import { ConsentDialog } from "@/components/ConsentDialog";
import { getConsent } from "@/lib/privacy";
import { startVoice, type VoiceLang } from "@/lib/voice";
import { RegionChip } from "@/components/RegionChip";
import { StatusChip } from "./ui";
import { useCropsy } from "./store";
import { isDebugView } from "@/lib/debugView";

const FARMER_LOADING_STEPS = ["Understanding your question…", "Checking field conditions…", "Preparing your advisory…"];
const PARCEL_CROP_REGISTRY = THEN_MALAI_PARCELS.map((p) => ({ id: p.id, crop: p.crop }));
const LAST_ID = `TM-${THEN_MALAI_PARCELS.length}`;

/** A new answer opens at its first line, not at its end: the chat stops following the bottom and brings the answer's top into view. */
function AnswerScroller({ id }: { id: string | null }) {
  const { stopScroll } = useStickToBottomContext();
  useEffect(() => {
    if (!id) return;
    const go = () => {
      stopScroll();
      document.getElementById("msg-" + id)?.scrollIntoView({ block: "start", behavior: "smooth" });
    };
    const t = [200, 900, 2000].map((ms) => window.setTimeout(go, ms));        // again after images and cards have loaded
    return () => t.forEach(window.clearTimeout);
  }, [id, stopScroll]);
  return null;
}

export function AskScreen({ initialParcel }: { initialParcel?: string | undefined }) {
  const c = useCropsy();
  const { selectedParcelId, userPicked, contextOn, currentParcel, searching, draft, setDraft, messages } = c;
  const [mapOpen, setMapOpen] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  // technical details (debug panel, verifier notes, model comparison, sources) show only in the development view: add ?debug=1 to the address once
  const debugView = useMemo(() => isDebugView(), []);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  useEffect(() => {
    if (!historyOpen) return;
    const close = (e: Event) => {
      if (e instanceof KeyboardEvent && e.key !== "Escape") return;
      if (e instanceof MouseEvent && (e.target as HTMLElement).closest?.("[data-testid=chat-history], [aria-label='Chat history']")) return;
      setHistoryOpen(false);
    };
    document.addEventListener("keydown", close);
    document.addEventListener("mousedown", close);
    return () => { document.removeEventListener("keydown", close); document.removeEventListener("mousedown", close); };
  }, [historyOpen]);
  const copyAnswer = (m: (typeof messages)[number]) => {
    const r = m.phase7Result;
    const text = r ? [r.answer, ...(r.recommendations ?? []).map((x, i) => `${i + 1}. ${x}`)].filter(Boolean).join("\n") : m.text;
    void navigator.clipboard?.writeText(text).then(() => {
      setCopiedId(m.id);
      window.setTimeout(() => setCopiedId(null), 1500);
    });
  };
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [loadingStepIndex, setLoadingStepIndex] = useState(0);
  const isDesktop = useMediaQuery("(min-width: 1024px)");
  const photoInput = useRef<HTMLInputElement>(null);
  const [consentOpen, setConsentOpen] = useState(false);
  const [consentWhy, setConsentWhy] = useState<string | undefined>(undefined);
  useEffect(() => {
    if (!getConsent().decided) setConsentOpen(true);
  }, []);
  const docInput = useRef<HTMLInputElement>(null);

  // the farmer drags the edge between map and chat to choose how wide the chat is (kept for next time); double-click resets it
  const gridRef = useRef<HTMLDivElement>(null);
  // start at the default so the server and the first browser render agree; the saved width is applied right after mount
  const [chatPct, setChatPct] = useState<number>(36);
  useEffect(() => {
    try {
      const v = Number(localStorage.getItem("cropsy.chatPct"));
      if (v >= 25 && v <= 65) setChatPct(v);
    } catch {
      /* no storage: keep the default */
    }
  }, []);
  const [dragging, setDragging] = useState(false);
  const setPct = (v: number) => {
    const n = Math.min(65, Math.max(25, Math.round(v * 10) / 10));
    setChatPct(n);
    try {
      localStorage.setItem("cropsy.chatPct", String(n));
    } catch {
      /* private mode: the width just is not remembered */
    }
  };
  const onDrag = (e: React.PointerEvent) => {
    const r = gridRef.current?.getBoundingClientRect();
    if (r && dragging) setPct(((r.right - e.clientX) / r.width) * 100);
  };

  // "Ask about this" from the alerts list lands here with ?parcel=TM-xx: that parcel joins the conversation
  useEffect(() => {
    if (initialParcel && THEN_MALAI_PARCELS.some((p) => p.id === initialParcel)) c.selectParcel(initialParcel);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialParcel]);

  useEffect(() => {
    if (!searching) {
      setLoadingStepIndex(0);
      return;
    }
    const timer = setInterval(() => setLoadingStepIndex((prev) => (prev + 1) % FARMER_LOADING_STEPS.length), 1800);
    return () => clearInterval(timer);
  }, [searching]);

  const parcelId = userPicked ? selectedParcelId : null;
  const crop = currentParcel?.crop;
  const parcel = currentParcel;
  const active = contextOn && parcelId ? parcelId : null;
  const stage = parcel ? parcel.stage.split(" - ")[0] : "";

  // Parcel suggestion matches while typing
  const suggestions = useMemo(() => {
    const trimmed = draft.trim().toLowerCase();
    if (!trimmed) return [];
    if (trimmed.startsWith("tm") || trimmed.startsWith("then") || trimmed.includes("tm-") || trimmed.includes("tm ")) {
      return PARCEL_CROP_REGISTRY.filter(
        (p) =>
          p.id.toLowerCase().includes(trimmed) ||
          p.crop.toLowerCase().includes(trimmed) ||
          `then malai ${p.id.replace("TM-", "")}`.includes(trimmed),
      ).slice(0, 8);
    }
    return [];
  }, [draft]);

  const [listening, setListening] = useState(false);
  const [voiceLang, setVoiceLang] = useState<VoiceLang>("ta-IN");
  const [voiceMsg, setVoiceMsg] = useState("");
  const stopVoice = useRef<null | (() => void)>(null);
  const toggleVoice = async () => {
    if (listening) { stopVoice.current?.(); return; }
    setVoiceMsg("");
    try {
      setListening(true);
      stopVoice.current = await startVoice(voiceLang, {
        partial: (t) => setDraft(t),
        final: (t) => setDraft(t),
        error: (m) => setVoiceMsg(m),
        end: () => { setListening(false); stopVoice.current = null; },
      });
    } catch (e) {
      setListening(false);
      const name = e instanceof Error ? e.name : "";
      setVoiceMsg(
        name === "NotAllowedError" ? "Microphone is blocked. Click the lock icon in the address bar, allow the microphone, then try again. (Embedded preview panes block it: open the app in Chrome.)"
        : name === "NotFoundError" ? "No microphone found on this device."
        : !window.isSecureContext ? "The microphone only works on https or localhost. Open the app from localhost or the deployed https address."
        : "Microphone not available. Please type the question.");
    }
  };

  const canSend = Boolean(draft.trim() || c.attachedImage || c.attachedDoc);
  const send = (text: string) => {
    setShowSuggestions(false);
    void c.ask(text);
  };
  // other parts of the app (the map's epidemic panel) can put a question into the chat
  const sendRef = useRef(send);
  sendRef.current = send;
  useEffect(() => {
    const h = (e: Event) => {
      const q = (e as CustomEvent<string>).detail;
      if (q) sendRef.current(q);
    };
    window.addEventListener("cropsy-ask", h);
    return () => window.removeEventListener("cropsy-ask", h);
  }, []);

  return (
    <div className="h-[calc(100vh-4rem)] min-h-[480px] md:h-screen">
      <ConsentDialog
        open={consentOpen}
        reason={consentWhy}
        onClose={(c) => {
          setConsentOpen(false);
          if (consentWhy && c.photos) setTimeout(() => photoInput.current?.click(), 50);
          setConsentWhy(undefined);
        }}
      />
      <div ref={gridRef} style={{ "--cols": `minmax(0,${100 - chatPct}fr) minmax(360px,${chatPct}fr)` } as React.CSSProperties} className={`relative grid h-full min-h-0 grid-cols-[minmax(0,1fr)] lg:[grid-template-columns:var(--cols)] ${dragging ? "select-none" : "transition-[grid-template-columns] duration-150"}`}>
        {/* GIS map and solar workspace */}
        <div className={`${mapOpen ? "flex" : "hidden"} min-h-0 flex-col border-r border-border lg:flex`}>
          {/* on a phone the map takes the whole screen, with a bar to get back to the chat */}
          <div className="flex h-12 shrink-0 items-center gap-2 border-b border-border px-2 lg:hidden">
            <Button size="sm" variant="ghost" onClick={() => setMapOpen(false)}>
              <ArrowLeft />
              Chat
            </Button>
            <span className="text-sm font-medium">Then Malai map</span>
            {selectedParcelId && <span className="ml-auto font-mono text-xs text-muted-foreground">{selectedParcelId}</span>}
          </div>
          <div className="relative min-h-0 flex-1">
            {(isDesktop || mapOpen) && <FieldMap selected={selectedParcelId ?? undefined} onSelect={c.selectParcel} />}
          </div>
        </div>

        {/* AI assistant */}
        <section className={`${mapOpen ? "hidden" : "flex"} relative min-h-0 min-w-0 flex-col bg-background lg:flex`}>
          <div
            role="separator"
            aria-orientation="vertical"
            aria-label="Drag to resize the chat. Double-click to reset."
            tabIndex={0}
            title="Drag to resize · double-click to reset"
            onPointerDown={(e) => {
              try {
                (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
              } catch {
                /* capture is only a convenience */
              }
              setDragging(true);
            }}
            onPointerMove={onDrag}
            onPointerUp={() => setDragging(false)}
            onPointerCancel={() => setDragging(false)}
            onDoubleClick={() => setPct(36)}
            onKeyDown={(e) => {
              if (e.key === "ArrowLeft") setPct(chatPct + 3);
              if (e.key === "ArrowRight") setPct(chatPct - 3);
            }}
            className="group absolute inset-y-0 -left-1.5 z-30 hidden w-3 cursor-col-resize touch-none items-center justify-center lg:flex"
          >
            <span className={`h-12 w-1 rounded-full transition-colors ${dragging ? "bg-primary" : "bg-border group-hover:bg-primary/70"}`} />
          </div>
          <header className="grid min-h-16 grid-cols-[minmax(0,1fr)_auto] items-center gap-3 border-b border-border px-4">
            <div className="flex min-w-0 items-center gap-3">
              <div className="grid size-9 shrink-0 place-items-center rounded-lg bg-primary text-primary-foreground">
                <Leaf className="size-4" />
              </div>
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <h1 className="truncate text-sm font-semibold">Cropsy</h1>
                  {active ? (
                    <span className="flex items-center gap-1 rounded-full border border-primary/40 bg-primary/10 px-2 py-0.5 font-mono text-[10px] text-primary">
                      <span>
                        {active} · {crop || "Field"}
                      </span>
                      <button
                        type="button"
                        onClick={c.toggleContext}
                        aria-label="Ask a general question instead"
                        title="Ask a general question instead (the map keeps this parcel selected)"
                        className="ml-1 hover:text-foreground"
                      >
                        <X className="size-3" />
                      </button>
                    </span>
                  ) : parcelId ? (
                    <button
                      type="button"
                      onClick={c.toggleContext}
                      title="Answer my questions for the parcel selected on the map"
                      className="rounded-full border border-border px-2 py-0.5 font-mono text-[10px] text-muted-foreground hover:border-primary/60 hover:text-primary"
                    >
                      + Use {parcelId}
                    </button>
                  ) : null}
                </div>
                <p className="truncate text-xs text-muted-foreground">
                  {active
                    ? `Field advisory · ${active} · ${crop || "Crop"}${parcel ? ` · ${stage}` : ""}`
                    : parcelId
                      ? `General advice · not using a parcel (map: ${parcelId})`
                      : "General agricultural advice · mention a parcel to get field advice"}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-1">
              <StatusChip tone={searching ? "warn" : "good"}>{searching ? "Preparing advisory…" : "Ready"}</StatusChip>
              <div className="relative">
                <Button size="icon" variant="ghost" aria-label="Chat history" aria-expanded={historyOpen} title="Earlier chats" className="min-h-10 min-w-10" onClick={() => setHistoryOpen((o) => !o)}>
                  <Clock />
                </Button>
                {historyOpen && (
                  <div className="absolute right-0 top-11 z-50 w-72 rounded-xl border border-border bg-overlay p-2 text-xs shadow-2xl" data-testid="chat-history">
                    <p className="px-2 pb-1 font-semibold">Earlier chats</p>
                    {c.history.length === 0 ? (
                      <p className="px-2 py-3 text-muted-foreground">No earlier chats yet. Press + to start a new one; the current chat is kept here.</p>
                    ) : (
                      <ul className="max-h-64 overflow-y-auto">
                        {c.history.map((h) => (
                          <li key={h.id} className="flex items-center gap-1">
                            <button type="button" className="min-w-0 flex-1 truncate rounded px-2 py-1.5 text-left hover:bg-accent" onClick={() => { c.openChat(h.id); setHistoryOpen(false); }}>
                              {h.title || "Chat"}
                              <span className="block text-[10px] text-muted-foreground">{new Date(h.savedAt).toLocaleString([], { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })}</span>
                            </button>
                            <button type="button" aria-label="Delete this chat" className="rounded p-1.5 text-muted-foreground hover:bg-accent hover:text-destructive" onClick={() => c.deleteChat(h.id)}>
                              <Trash2 className="size-3.5" />
                            </button>
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                )}
              </div>
              <Button size="icon" variant="ghost" aria-label="New chat" title="New chat" className="min-h-10 min-w-10" onClick={() => { c.newChat(); setHistoryOpen(false); }}>
                <Plus />
              </Button>
            </div>
          </header>

          <Button variant="secondary" className="mx-4 mt-3 lg:hidden" onClick={() => setMapOpen(true)}>
            <Map />
            Open map
          </Button>

          <Conversation className="min-h-0">
            <AnswerScroller id={messages[messages.length - 1]?.sender === "cropsy" ? messages[messages.length - 1].id : null} />
            <ConversationContent className="gap-5 p-4">
              {messages.length === 0 && !searching && (
                <div className="my-auto flex flex-col items-center gap-3 px-2 py-6 text-center">
                  <div className="grid size-14 place-items-center rounded-2xl border border-primary/40 bg-primary/15 text-primary shadow-lg">
                    <Sprout size={28} />
                  </div>
                  <h2 className="text-lg font-semibold">Cropsy Agricultural AI</h2>
                  <p className="max-w-xs text-xs text-muted-foreground">
                    {active
                      ? `Active context: ${active} (${crop}${parcel ? `, ${parcel.stage}` : ""}${parcel && parcel.issueCode !== "healthy" ? `, ${parcel.issue} reported` : ""}). Ask about fertilizer, weather, soil or pests, or attach a photo.`
                      : `General question mode. Ask any crop question, or select a parcel on the map, or type one (TM-01 to ${LAST_ID}).`}
                  </p>
                  <span className="mt-2 font-mono text-[10px] uppercase tracking-wider text-muted-foreground">Suggested questions</span>
                  <div className="flex w-full max-w-[320px] flex-col gap-2">
                    {c.chips.map((chip) => (
                      <Button key={chip.label} variant="outline" size="sm" className="h-auto whitespace-normal rounded-full py-2 text-xs" onClick={() => send(chip.query)}>
                        {chip.label}
                      </Button>
                    ))}
                  </div>
                </div>
              )}

              {messages.map((m) =>
                m.sender === "user" ? (
                  <Message key={m.id} from="user">
                    <MessageContent>
                      <div className="flex justify-between gap-6 font-mono text-[10px] text-muted-foreground">
                        <span className="font-semibold text-primary">Farmer</span>
                        <span>{m.timestamp}</span>
                      </div>
                      {m.imagePreview && (
                        <div className="overflow-hidden rounded-lg border border-border bg-black/40">
                          <img src={m.imagePreview} alt="Uploaded field" className="max-h-40 w-auto rounded object-cover" />
                          <div className="flex items-center gap-1 p-1 text-[10px] text-muted-foreground">
                            <Camera className="size-3 text-primary" />
                            <span>📷 {m.imageName || "Field Photograph"}</span>
                          </div>
                        </div>
                      )}
                      <p className="select-text text-sm leading-relaxed">{m.text}</p>
                    </MessageContent>
                  </Message>
                ) : (
                  <Message key={m.id} from="assistant" id={"msg-" + m.id}>
                    <MessageContent className="w-full min-w-0 max-w-full">
                      <div className="flex items-center justify-between px-1">
                        <span className="flex items-center gap-1.5 text-xs font-semibold text-primary">
                          <Sprout className="size-3.5" /> Cropsy
                        </span>
                        <span className="font-mono text-[10px] text-muted-foreground">{m.timestamp}</span>
                      </div>
                      <div className="min-w-0 max-w-full overflow-hidden px-1 py-1">
                        {m.phase7Result ? (
                          <Phase7AdvisoryCard result={m.phase7Result} parcelId={m.parcelId} onSelectParcel={c.selectParcel} onAskFollowUp={(q) => send(q)} />
                        ) : (
                          <div className="select-text text-sm leading-relaxed">{m.text}</div>
                        )}
                      </div>
                      <div className="flex items-center gap-1 px-1 text-muted-foreground">
                        {m.error ? (
                          <Button size="sm" variant="outline" className="h-7 gap-1 text-xs" onClick={() => c.regenerate(m.id)}>
                            <RefreshCw className="size-3" /> Try again
                          </Button>
                        ) : (
                          <>
                            <button type="button" aria-label="Copy answer" title="Copy answer" className="rounded p-1.5 hover:bg-accent hover:text-foreground focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary" onClick={() => copyAnswer(m)}>
                              {copiedId === m.id ? <Check className="size-3.5 text-success" /> : <Copy className="size-3.5" />}
                            </button>
                            <button type="button" aria-label="Ask again" title="Ask again" className="rounded p-1.5 hover:bg-accent hover:text-foreground focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary" onClick={() => c.regenerate(m.id)} disabled={searching}>
                              <RefreshCw className="size-3.5" />
                            </button>
                            {m.phase7Result && <FeedbackButtons result={m.phase7Result} />}
                          </>
                        )}
                      </div>
                    </MessageContent>
                  </Message>
                ),
              )}

              {searching && (
                <div data-testid="chat-loading-state" className="flex animate-pulse items-center gap-2.5 rounded-xl border border-border bg-muted/40 p-3 text-xs">
                  <Loader2 className="size-4 animate-spin text-primary" />
                  <span className="font-medium tracking-wide text-success">{FARMER_LOADING_STEPS[loadingStepIndex]}</span>
                </div>
              )}
            </ConversationContent>
            <ConversationScrollButton />
          </Conversation>

          {/* Real-time parcel auto-suggestions */}
          {suggestions.length > 0 && showSuggestions && (
            <div className="border-t border-border bg-card p-2">
              <div className="mb-1 px-1 font-mono text-[10px] text-muted-foreground">Matching Then Malai Parcels:</div>
              <div className="flex max-h-24 flex-wrap gap-1.5 overflow-y-auto">
                {suggestions.map((s) => (
                  <button
                    key={s.id}
                    type="button"
                    onClick={() => {
                      c.selectParcel(s.id);
                      setShowSuggestions(false);
                    }}
                    className="flex items-center gap-1 rounded border border-border bg-muted px-2 py-1 text-xs hover:border-primary hover:bg-primary/15"
                  >
                    <span className="font-bold text-primary">{s.id}</span>
                    <span className="text-[11px] text-muted-foreground">({s.crop})</span>
                  </button>
                ))}
              </div>
            </div>
          )}

          <div className="border-t border-border px-2 py-1.5">
            <PromptInput onSubmit={() => send(draft)} className="rounded-xl border-border bg-card">
              {(c.attachedImage || c.attachedDoc) && (
                <PromptInputHeader>
                  <div className="flex flex-wrap gap-2">
                    {c.attachedImage && (
                      <span className="flex items-center gap-2 rounded-lg border border-border bg-muted py-1 pl-1 pr-2 text-[11px]">
                        {c.attachedImagePreview && <img src={c.attachedImagePreview} alt="" className="size-6 rounded object-cover" />}
                        <span className="max-w-[140px] truncate">{c.attachedImage.name}</span>
                        <button type="button" onClick={c.clearImage} aria-label="Remove image">
                          <X className="size-3" />
                        </button>
                      </span>
                    )}
                    {c.attachedDoc && (
                      <span className="flex items-center gap-1.5 rounded-lg border border-border bg-muted px-2 py-1 text-[11px]">
                        <FileText className="size-3" />
                        <span className="max-w-[140px] truncate">{c.attachedDoc.name}</span>
                        <button type="button" onClick={c.clearDoc} aria-label="Remove document">
                          <X className="size-3" />
                        </button>
                      </span>
                    )}
                  </div>
                </PromptInputHeader>
              )}
              <PromptInputTextarea
                value={draft}
                onPaste={(e) => {
                  // paste a screenshot or copied image straight into the chat (same consent as the camera button)
                  const file = Array.from(e.clipboardData?.items ?? []).find((it) => it.kind === "file" && it.type.startsWith("image/"))?.getAsFile();
                  if (!file) return;
                  e.preventDefault();
                  if (getConsent().photos) c.pickImage(file);
                  else {
                    setConsentWhy("To look at your photo, Cropsy needs your permission first.");
                    setConsentOpen(true);
                  }
                }}
                onFocus={() => setShowSuggestions(true)}
                onChange={(e) => {
                  setDraft(e.currentTarget.value);
                  setShowSuggestions(true);
                }}
                placeholder={active ? `Ask about ${active}…` : `Ask a crop question or type TM-01…${LAST_ID}`}
                maxLength={1000}
                className="min-h-8 py-1.5 text-[13px] leading-snug"
                rows={1}
              />
              <PromptInputFooter className="px-1.5 pb-1 pt-0 [&_button]:size-7">
                <PromptInputTools>
                  <PromptInputButton aria-label="Attach crop photo" tooltip="Attach crop photo" onClick={() => {
                    if (getConsent().photos) photoInput.current?.click();
                    else {
                      setConsentWhy("To look at your photo, Cropsy needs your permission first.");
                      setConsentOpen(true);
                    }
                  }}>
                    <Camera />
                  </PromptInputButton>
                  <PromptInputButton aria-label="Attach document" tooltip="Attach document" onClick={() => docInput.current?.click()}>
                    <FileText />
                  </PromptInputButton>
                  <PromptInputButton
                    aria-label="Voice query"
                    tooltip="Voice query"
                    onClick={() => void toggleVoice()}
                  >
                    <Mic className={listening ? "animate-pulse text-destructive" : ""} />
                  </PromptInputButton>
                  <PromptInputButton aria-label="Voice language" tooltip="Voice language (Tamil or English)" onClick={() => setVoiceLang((l) => (l === "ta-IN" ? "en-IN" : "ta-IN"))}>
                    <span className="text-[10px] font-semibold">{voiceLang === "ta-IN" ? "தமி" : "EN"}</span>
                  </PromptInputButton>
                  <RegionChip />
                  {(listening || voiceMsg) && <span className="px-1 text-[10.5px] text-muted-foreground" role="status">{listening ? "Listening… tap the mic to stop" : voiceMsg}</span>}
                </PromptInputTools>
                <PromptInputSubmit status={searching ? "submitted" : "ready"} disabled={!canSend || searching} className="size-8" />
              </PromptInputFooter>
              <input
                ref={photoInput}
                type="file"
                hidden
                accept="image/*"
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) c.pickImage(f);
                  e.target.value = "";
                }}
              />
              <input
                ref={docInput}
                type="file"
                hidden
                accept=".pdf,.doc,.docx,.txt,.csv"
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) c.pickDoc(f);
                  e.target.value = "";
                }}
              />
            </PromptInput>
            {debugView && <p className="mt-1 truncate text-center text-[10px] text-muted-foreground">Development view: verify field decisions with a local extension officer. Parcel records in this demo village are dummy data.</p>}
          </div>
        </section>
      </div>
    </div>
  );
}
