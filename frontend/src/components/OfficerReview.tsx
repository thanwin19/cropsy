import { useEffect, useState } from "react";
import { getApiSettings, type FeedbackRow } from "@/lib/cropsy-api";

type Correction = { id: string; time: string; query: string; corrected_answer: string; officer: string; parcel_id?: string | null; note?: string };

const base = () => (getApiSettings().baseUrl || "").replace(/\/$/, "");
const field = "w-full rounded-lg border border-border bg-background px-3 py-2 text-[12px]";

/** Officer review: answers farmers marked not helpful, with a form to write the correct answer. The corrected text is then shown for the same question. */
export function OfficerReview({ feedback }: { feedback: FeedbackRow[] }) {
  const [officer, setOfficer] = useState("");
  const [key, setKey] = useState("");
  const [open, setOpen] = useState<FeedbackRow | null>(null);
  const [text, setText] = useState("");
  const [note, setNote] = useState("");
  const [msg, setMsg] = useState("");
  const [rows, setRows] = useState<Correction[]>([]);

  const load = () =>
    fetch(`${base()}/api/corrections`)
      .then((r) => r.json())
      .then((d) => setRows(Array.isArray(d.items) ? d.items : []))
      .catch(() => setRows([]));

  useEffect(() => {
    try {
      setOfficer(sessionStorage.getItem("cropsy.officer") || "");
      setKey(sessionStorage.getItem("cropsy.officerKey") || "");
    } catch {
      /* no storage */
    }
    void load();
  }, []);

  const headers = () => ({ "Content-Type": "application/json", ...(key ? { "X-Officer-Key": key } : {}) });

  async function save() {
    if (!open) return;
    try {
      sessionStorage.setItem("cropsy.officer", officer);
      sessionStorage.setItem("cropsy.officerKey", key);
    } catch {
      /* ignore */
    }
    const r = await fetch(`${base()}/api/corrections`, { method: "POST", headers: headers(), body: JSON.stringify({ query: open.query, corrected_answer: text, officer, parcel_id: open.parcel_id ?? null, note }) });
    if (r.ok) {
      setMsg("Saved. The next farmer who asks this question will see your answer, marked officer-reviewed.");
      setOpen(null);
      setText("");
      setNote("");
      void load();
    } else {
      const d = await r.json().catch(() => ({}));
      setMsg(r.status === 403 ? "Not allowed: enter the officer key." : `Could not save: ${d.detail ?? r.status}`);
    }
  }

  async function remove(id: string) {
    const r = await fetch(`${base()}/api/corrections/${id}`, { method: "DELETE", headers: headers() });
    setMsg(r.ok ? "Removed." : r.status === 403 ? "Not allowed: enter the officer key." : "Could not remove.");
    void load();
  }

  const bad = feedback.filter((f) => !f.helpful);
  return (
    <section className="mt-6 rounded-2xl border border-border bg-card p-5" data-testid="officer-review">
      <h2 className="text-[13px] font-extrabold">Officer review: correct an answer</h2>
      <p className="mt-1 text-[11px] text-muted-foreground">Pick an answer a farmer marked not helpful, write the right guidance, and sign it. Only officers should do this.</p>
      <div className="mt-3 grid gap-2 sm:grid-cols-2">
        <input className={field} placeholder="Your name and designation" value={officer} onChange={(e) => setOfficer(e.target.value)} />
        <input className={field} type="password" placeholder="Officer key (if set on the server)" value={key} onChange={(e) => setKey(e.target.value)} />
      </div>
      {msg && <p className="mt-2 text-[11px] text-primary">{msg}</p>}

      {bad.length === 0 ? (
        <p className="mt-3 text-[12px] text-muted-foreground">No not-helpful answers to review yet.</p>
      ) : (
        <ul className="mt-3 divide-y divide-border text-[12px]">
          {bad.map((f) => (
            <li key={f.time + f.query} className="py-2">
              <div className="flex items-start justify-between gap-3">
                <span className="min-w-0 break-words font-medium">{f.query}</span>
                <button type="button" onClick={() => { setOpen(f); setText(""); }} className="shrink-0 rounded-full border border-primary/50 bg-primary/10 px-3 py-1 text-[11px] font-medium text-primary">Write correction</button>
              </div>
              {f.answer && <p className="mt-1 text-[11px] text-muted-foreground">Cropsy answered: {f.answer.slice(0, 300)}{f.answer.length > 300 ? "…" : ""}</p>}
              {open === f && (
                <div className="mt-2 grid gap-2">
                  <textarea className={field} rows={4} placeholder="The correct answer for the farmer (plain words, no invented doses)" value={text} onChange={(e) => setText(e.target.value)} />
                  <input className={field} placeholder="Source or note (for example: TNAU CPG 2020 p. 45)" value={note} onChange={(e) => setNote(e.target.value)} />
                  <div className="flex gap-2">
                    <button type="button" onClick={() => void save()} disabled={text.trim().length < 10 || !officer.trim()} className="rounded-lg bg-primary px-4 py-2 text-[11px] font-bold text-primary-foreground disabled:opacity-40">Save correction</button>
                    <button type="button" onClick={() => setOpen(null)} className="rounded-lg border border-border px-4 py-2 text-[11px]">Cancel</button>
                  </div>
                </div>
              )}
            </li>
          ))}
        </ul>
      )}

      <h3 className="mt-5 text-[12px] font-bold">Saved corrections ({rows.length})</h3>
      {rows.length === 0 ? (
        <p className="mt-1 text-[12px] text-muted-foreground">None yet.</p>
      ) : (
        <ul className="mt-2 divide-y divide-border text-[12px]">
          {rows.map((c) => (
            <li key={c.id} className="flex items-start justify-between gap-3 py-2">
              <span className="min-w-0 break-words"><b>{c.query}</b><span className="block text-muted-foreground">{c.corrected_answer.slice(0, 200)}{c.corrected_answer.length > 200 ? "…" : ""} (by {c.officer})</span></span>
              <button type="button" onClick={() => void remove(c.id)} className="shrink-0 text-[11px] text-destructive hover:underline">Remove</button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
