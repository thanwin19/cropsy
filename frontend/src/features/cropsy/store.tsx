import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { useNavigate } from "@tanstack/react-router";
import {
  fetchAlerts,
  fetchFieldReport,
  submitAdvisory,
  resetConversationContext,
  type ExecutionRecord,
  type FieldReport,
  type Phase7AdvisoryResult,
  getApiSettings,
} from "@/lib/cropsy-api";
import { THEN_MALAI_PARCELS } from "@/lib/parcels";
import { isGeneralQuestion } from "./generalQuestion";
import type { VillageParcel } from "@/data/villageParcels.generated";

/**
 * The state that used to live in the old Home page, lifted into a provider so it survives moving between the four screens:
 * the chat, the selected parcel, the attachments, the most recent real answer (Trust and Latest advisory read it), the alert count
 * and the print report. Behaviour is unchanged from the old app:
 *   - general advisory is the default; a parcel joins the conversation only when the user picks it on the map or types its id;
 *   - the map always keeps one parcel highlighted for its sun and shadow panels, but until the user picks one it is not "asked about".
 */
export interface ChatMessage {
  id: string;
  sender: "user" | "cropsy";
  text: string;
  timestamp: string;
  record?: ExecutionRecord;
  phase7Result?: Phase7AdvisoryResult;
  isPhase7?: boolean;
  parcelId?: string | null;
  imagePreview?: string | null;
  imageName?: string | undefined;
  /** a failed request: the chat shows it with a Retry button */
  error?: boolean;
}

/** An earlier conversation kept in this browser so a new chat does not lose it. */
export interface ChatSession {
  id: string;
  title: string;
  savedAt: number;
  messages: ChatMessage[];
}


export type Chip = { label: string; query: string };

// Suggested questions. With a parcel in context they are built from that parcel's real crop, stage and issue;
// without one they are general questions that need no parcel.
const GENERAL_CHIPS: Chip[] = [
  { label: "🌾 nel payirukku urea eppo podanum?", query: "nel payirukku urea eppo podanum?" },
  { label: "🌧️ rice leaf yellow + rain tomorrow", query: "rice leaf yellow + rain tomorrow" },
  { label: "🦠 How do I manage sheath blight in rice?", query: "How do I manage sheath blight in rice?" },
  { label: "🥥 Coconut ku potash eppo, evlo podanum?", query: "Coconut ku potash eppo, evlo podanum?" },
];

function parcelChips(p: VillageParcel): Chip[] {
  const stage = p.stage.split(" - ")[0]; // keep chips short ("Mature bearing palm - nut development phase" -> "Mature bearing palm")
  const chips: Chip[] = [];
  if (p.issueCode !== "healthy") {
    chips.push({
      label: `⚠️ ${p.issue} at ${p.id}: how serious?`,
      query: `${p.id} shows ${p.issue}. How serious is it and what should I do?`,
    });
  }
  chips.push({ label: `🌧️ Rain this week: spray ${p.id}?`, query: `Will it rain at ${p.id} this week? Should I spray or fertilize now?` });
  chips.push({ label: `🌱 ${p.crop} (${stage}): fertilizer plan`, query: `What fertilizer does ${p.id} need at the ${p.stage} stage?` });
  chips.push({ label: `💧 Irrigate ${p.id} today?`, query: `Does ${p.id} need irrigation today?` });
  return chips;
}

// "tm 45", "TM-045", "tm-7" -> the village's parcel id, if that parcel exists
export const parcelFromText = (text: string): string | null => {
  const m = text.match(/\bTM[-\s]?0*(\d{1,3})\b/i);
  if (!m) return null;
  const n = Number(m[1]);
  const id = `TM-${n < 100 ? String(n).padStart(2, "0") : n}`;
  return THEN_MALAI_PARCELS.some((p) => p.id === id) ? id : null;
};

const now = () => new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

type CropsyContextValue = {
  selectedParcelId: string | null;
  /** parcel id for screens that always need one (the map keeps TM-01 highlighted by default) */
  parcelOrDefault: string;
  userPicked: boolean;
  contextOn: boolean;
  currentParcel: VillageParcel | null;
  chips: Chip[];
  draft: string;
  setDraft: (v: string) => void;
  messages: ChatMessage[];
  searching: boolean;
  attachedImage: File | null;
  attachedImagePreview: string | null;
  attachedDoc: File | null;
  lastResult: Phase7AdvisoryResult | null;
  alertCount: number;
  printReport: FieldReport | null;
  printing: boolean;
  selectParcel: (id: string) => void;
  toggleContext: () => void;
  ask: (query: string) => Promise<void>;
  pickImage: (f: File) => void;
  pickDoc: (f: File) => void;
  clearImage: () => void;
  clearDoc: () => void;
  clearChat: () => void;
  newChat: () => void;
  history: ChatSession[];
  openChat: (id: string) => void;
  deleteChat: (id: string) => void;
  regenerate: (messageId: string) => void;
  print: () => Promise<void>;
  closePrint: () => void;
};

const Ctx = createContext<CropsyContextValue | null>(null);

export function useCropsy(): CropsyContextValue {
  const v = useContext(Ctx);
  if (!v) throw new Error("useCropsy must be used inside <CropsyProvider>");
  return v;
}

export function CropsyProvider({ children }: { children: ReactNode }) {
  const navigate = useNavigate();
  const [printReport, setPrintReport] = useState<FieldReport | null>(null);
  const [printing, setPrinting] = useState(false);
  const [alertCount, setAlertCount] = useState(0);
  // General advisory is the default. A parcel joins the conversation only when the user asks about it
  // (types its id) or picks it on the map. The map always keeps one parcel highlighted for its sun/shadow panels,
  // but until the user picks one it is not treated as a parcel the farmer asked about.
  const [selectedParcelId, setSelectedParcelId] = useState<string | null>("TM-01");
  const [userPicked, setUserPicked] = useState(false);
  const [contextOn, setContextOn] = useState(false);
  const [draft, setDraft] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [searching, setSearching] = useState(false);
  const [attachedImage, setAttachedImage] = useState<File | null>(null);
  const [attachedImagePreview, setAttachedImagePreview] = useState<string | null>(null);
  const [attachedDoc, setAttachedDoc] = useState<File | null>(null);
  const advisoryRequestGen = useRef(0);
  const [history, setHistory] = useState<ChatSession[]>([]);
  useEffect(() => {
    try {
      const h = JSON.parse(localStorage.getItem("cropsy.history") || "[]");
      if (Array.isArray(h)) setHistory(h.filter((s) => s && Array.isArray(s.messages)));
    } catch {
      /* no storage: no history */
    }
  }, []);
  const saveHistory = useCallback((h: ChatSession[]) => {
    setHistory(h);
    try {
      localStorage.setItem("cropsy.history", JSON.stringify(h));
    } catch {
      /* storage full or blocked */
    }
  }, []);

  // the last few answers are kept in this browser so they can still be read with no network (cleared by Delete my data)
  const chatLoaded = useRef(false);
  useEffect(() => {
    try {
      const saved = JSON.parse(localStorage.getItem("cropsy.chat") || "[]");
      if (Array.isArray(saved) && saved.length) setMessages((cur) => (cur.length ? cur : saved));
    } catch {
      /* no storage or bad data: start empty */
    }
    chatLoaded.current = true;
  }, []);
  useEffect(() => {
    if (!chatLoaded.current) return;
    try {
      const keep = messages.slice(-12).map((m) => ({ ...m, imagePreview: null, record: undefined }));
      localStorage.setItem("cropsy.chat", JSON.stringify(keep));
    } catch {
      /* storage full or blocked: skip */
    }
  }, [messages]);

  const selectParcel = useCallback((id: string) => {
    setSelectedParcelId(id);
    setUserPicked(true);
    setContextOn(true); // picking a parcel means "talk about this one"
    advisoryRequestGen.current += 1;
    setSearching(false);
  }, []);

  const toggleContext = useCallback(() => setContextOn((v) => !v), []);

  const clearImage = useCallback(() => {
    setAttachedImagePreview((prev) => {
      if (prev) URL.revokeObjectURL(prev);
      return null;
    });
    setAttachedImage(null);
  }, []);

  const pickImage = useCallback((f: File) => {
    setAttachedImagePreview((prev) => {
      if (prev) URL.revokeObjectURL(prev);
      return URL.createObjectURL(f);
    });
    setAttachedImage(f);
  }, []);

  const ask = useCallback(
    async (queryText: string) => {
      let clean =
        queryText.trim() ||
        (attachedImage
          ? `Classify crop and growth stage from attached photo ${attachedImage.name}`
          : attachedDoc
            ? `Extract and explain land document records from ${attachedDoc.name}`
            : "");
      if (!clean) return;
      // a document is read first (PDF text, Textract, or Ministral vision for Tamil scans); its text goes to the server with the question, but the chat shows only the farmer's words and the file name
      let sent = clean;
      if (attachedDoc) {
        try {
          const dataUrl: string = await new Promise((res, rej) => { const fr = new FileReader(); fr.onload = () => res(String(fr.result)); fr.onerror = () => rej(fr.error); fr.readAsDataURL(attachedDoc); });
          const base = (getApiSettings().baseUrl || "").replace(/\/$/, "");
          const r = await fetch(`${base}/api/document`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ data_url: dataUrl }) });
          const j = await r.json();
          sent = r.ok ? `${clean}\n\n[Text read from ${attachedDoc.name}: ${String(j.text)}]` : `${clean}\n[Could not read ${attachedDoc.name}: ${j.detail ?? r.status}]`;
        } catch {
          sent = `${clean}\n[Could not read ${attachedDoc.name}]`;
        }
        clean = `${clean} 📎 ${attachedDoc.name}`;
      }

      // A parcel typed in the question wins, selects it on the map and turns context on.
      const mentioned = parcelFromText(clean);
      if (mentioned && (mentioned !== selectedParcelId || !contextOn)) {
        setSelectedParcelId(mentioned);
        setUserPicked(true);
        setContextOn(true);
      }
      let effectiveParcel = mentioned ?? (contextOn ? selectedParcelId : null);
      // a selected parcel stays in the chat, but a general or different-crop question is answered as a general question (not forced into the parcel's record)
      if (effectiveParcel && !mentioned) {
        const pc = THEN_MALAI_PARCELS.find((p) => p.id === effectiveParcel)?.crop ?? null;
        if (isGeneralQuestion(clean, pc)) effectiveParcel = null;
      }
      const parcel = effectiveParcel || undefined;
      const gen = ++advisoryRequestGen.current;
      void navigate({ to: "/" }); // answers appear in the chat

      const currentImagePreview = attachedImagePreview;
      const currentImageName = attachedImage?.name;
      const currentAttachedImage = attachedImage;

      setMessages((p) => [
        ...p,
        {
          id: "u-" + Date.now(),
          sender: "user",
          text: clean,
          timestamp: now(),
          parcelId: effectiveParcel,
          imagePreview: currentImagePreview,
          imageName: currentImageName,
        },
      ]);
      setDraft("");
      // the preview URL now belongs to the sent message, so only drop the attachment, not the object URL
      setAttachedImage(null);
      setAttachedImagePreview(null);
      setAttachedDoc(null);

      setSearching(true);
      try {
        const result = await submitAdvisory(sent, parcel, currentAttachedImage);
        if (gen !== advisoryRequestGen.current) return;

        // If the backend resolved a different parcel for a parcel question, follow it. General questions stay general.
        if (effectiveParcel && result.parcel_id && result.parcel_id !== effectiveParcel) {
          setSelectedParcelId(result.parcel_id);
        }

        const text = result.answer || result.recommendations?.[0] || "Advisory generated successfully.";
        setMessages((p) => [
          ...p,
          {
            id: "c-" + Date.now(),
            sender: "cropsy",
            text,
            timestamp: now(),
            phase7Result: result,
            isPhase7: true,
            parcelId: effectiveParcel ? result.parcel_id || effectiveParcel : null,
          },
        ]);
      } catch (err: any) {
        if (gen !== advisoryRequestGen.current) return;
        setDraft(clean);
        const errMsg = err?.message || "connection could not be established";
        setMessages((p) => [
          ...p,
          {
            id: "c-err-" + Date.now(),
            sender: "cropsy",
            timestamp: now(),
            parcelId: effectiveParcel,
            error: true,
            text: `Cropsy could not get an answer (${errMsg}). Check your connection and try again.`,
          },
        ]);
      } finally {
        if (gen === advisoryRequestGen.current) setSearching(false);
      }
    },
    [selectedParcelId, contextOn, attachedImage, attachedDoc, attachedImagePreview, navigate],
  );

  // archive the current conversation (if the farmer asked anything) and start a fresh one
  const newChat = useCallback(() => {
    const asked = messages.filter((m) => m.sender === "user");
    if (asked.length) {
      const session: ChatSession = { id: "s-" + Date.now(), title: asked[0].text.slice(0, 60), savedAt: Date.now(), messages: messages.slice(-24).map((m) => ({ ...m, imagePreview: null, record: undefined })) };
      saveHistory([session, ...history].slice(0, 15));
    }
    advisoryRequestGen.current += 1;
    resetConversationContext();
    setSearching(false);
    setMessages([]);
  }, [messages, history, saveHistory]);
  const openChat = useCallback((id: string) => {
    const s = history.find((x) => x.id === id);
    if (!s) return;
    const asked = messages.filter((m) => m.sender === "user");
    const rest = history.filter((x) => x.id !== id);
    if (asked.length) rest.unshift({ id: "s-" + Date.now(), title: asked[0].text.slice(0, 60), savedAt: Date.now(), messages: messages.slice(-24).map((m) => ({ ...m, imagePreview: null, record: undefined })) });
    saveHistory(rest.slice(0, 15));
    resetConversationContext();
    setMessages(s.messages);
  }, [history, messages, saveHistory]);
  const deleteChat = useCallback((id: string) => saveHistory(history.filter((x) => x.id !== id)), [history, saveHistory]);
  // ask the same question again (text questions only: an attached photo or document is not kept after sending)
  const regenerate = useCallback((messageId: string) => {
    const i = messages.findIndex((m) => m.id === messageId);
    const q = [...messages.slice(0, i)].reverse().find((m) => m.sender === "user");
    if (q && !q.imageName && !q.text.includes("📎")) void ask(q.text);
  }, [messages, ask]);

  const currentParcel = selectedParcelId ? THEN_MALAI_PARCELS.find((p) => p.id === selectedParcelId) || THEN_MALAI_PARCELS[0] || null : null;
  const chips = useMemo(
    () => (contextOn && userPicked && currentParcel ? parcelChips(currentParcel) : GENERAL_CHIPS),
    [contextOn, userPicked, currentParcel],
  );

  const print = useCallback(async () => {
    setPrinting(true);
    try {
      setPrintReport(await fetchFieldReport(selectedParcelId || "TM-01"));
    } catch {
      /* backend offline: nothing to print */
    } finally {
      setPrinting(false);
    }
  }, [selectedParcelId]);

  useEffect(() => {
    fetchAlerts("high").then((a) => setAlertCount(a.count)).catch(() => undefined);
  }, []);

  // The detail panels (evidence, trace, advisory) all show the most recent real answer
  const lastResult = useMemo(() => [...messages].reverse().find((m) => m.phase7Result)?.phase7Result ?? null, [messages]);

  const value: CropsyContextValue = {
    selectedParcelId,
    parcelOrDefault: selectedParcelId || "TM-01",
    userPicked,
    contextOn,
    currentParcel,
    chips,
    draft,
    setDraft,
    messages,
    searching,
    attachedImage,
    attachedImagePreview,
    attachedDoc,
    lastResult,
    alertCount,
    printReport,
    printing,
    selectParcel,
    toggleContext,
    ask,
    pickImage,
    pickDoc: setAttachedDoc,
    clearImage,
    clearDoc: () => setAttachedDoc(null),
    clearChat: newChat,
    newChat,
    history,
    openChat,
    deleteChat,
    regenerate,
    print,
    closePrint: () => setPrintReport(null),
  };

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}
