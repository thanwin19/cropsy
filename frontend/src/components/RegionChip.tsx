import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { MapPin } from "lucide-react";
import { getRegionProfile, regionIsSaved, setRegionProfile, type RegionProfile } from "@/lib/privacy";

const STATES = ["Andhra Pradesh", "Assam", "Bihar", "Chhattisgarh", "Delhi", "Goa", "Gujarat", "Haryana", "Himachal Pradesh", "Jharkhand", "Karnataka", "Kerala", "Madhya Pradesh", "Maharashtra", "Odisha", "Puducherry", "Punjab", "Rajasthan", "Tamil Nadu", "Telangana", "Uttar Pradesh", "Uttarakhand", "West Bengal", "Other state or country"];

/** The farmer's location, optional. Without it Cropsy answers with Tamil Nadu (TNAU) evidence and says so. It is kept on this device only if the farmer ticks the box. */
export function RegionChip() {
  const [open, setOpen] = useState(false);
  const [r, setR] = useState<RegionProfile | null>(null);
  const [state, setState] = useState("");
  const [district, setDistrict] = useState("");
  const [remember, setRemember] = useState(false);
  const btn = useRef<HTMLButtonElement>(null);
  const [pos, setPos] = useState({ left: 8, bottom: 8 });

  useEffect(() => {
    const cur = getRegionProfile();
    setR(cur);
    setState(cur?.state ?? "");
    setDistrict(cur?.district ?? "");
    setRemember(regionIsSaved());
  }, []);

  const save = () => {
    const next: RegionProfile | null = state ? { country: "India", state: state === "Other state or country" ? undefined : state, district: district.trim() || undefined } : district.trim() ? { country: "India", district: district.trim() } : null;
    setRegionProfile(next, remember);
    setR(next);
    setOpen(false);
  };
  const clear = () => {
    setRegionProfile(null, false);
    setR(null);
    setState("");
    setDistrict("");
    setRemember(false);
    setOpen(false);
  };
  const label = r?.district ? `${r.district}${r.state ? ", " + r.state : ""}` : r?.state ?? "Region";

  return (
    <span className="relative">
      <button type="button" ref={btn} onClick={() => {
          const b = btn.current?.getBoundingClientRect();
          if (b) setPos({ left: Math.max(8, Math.min(b.left, window.innerWidth - 264)), bottom: window.innerHeight - b.top + 6 });
          setOpen((o) => !o);
        }} aria-label="Set your region" aria-expanded={open} title="Your state or district: sowing time, varieties and doses depend on it"
        className="inline-flex h-7 items-center gap-1 rounded-md border border-border px-1.5 text-[10.5px] text-muted-foreground hover:bg-accent" data-testid="region-chip">
        <MapPin className="size-3.5" /> {label}
      </button>
      {open && createPortal(
        <div style={{ position: "fixed", left: pos.left, bottom: pos.bottom }} className="z-[100] w-64 rounded-xl border border-border bg-overlay p-3 text-xs text-foreground shadow-2xl" data-testid="region-popover">
          <p className="mb-1 font-semibold">Where is your farm?</p>
          <p className="mb-2 text-[10.5px] text-muted-foreground">Optional. Without it, answers use Tamil Nadu (TNAU) evidence and say so. Other states have no region-checked source yet, so you get labelled general guidance.</p>
          <label className="mb-1 grid gap-0.5">State
            <select value={state} onChange={(e) => setState(e.target.value)} className="rounded border border-border bg-background px-1.5 py-1">
              <option value="">Not set</option>
              {STATES.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </label>
          <label className="mb-1 grid gap-0.5">District (optional)
            <input value={district} onChange={(e) => setDistrict(e.target.value)} placeholder="e.g. Tenkasi" className="rounded border border-border bg-background px-1.5 py-1" />
          </label>
          <label className="mb-2 flex items-start gap-1.5 text-[10.5px]"><input type="checkbox" checked={remember} onChange={(e) => setRemember(e.target.checked)} className="mt-0.5" /> Remember on this device (saved in this browser only; you can clear it any time)</label>
          <div className="flex gap-2">
            <button type="button" onClick={save} className="rounded-lg bg-primary px-3 py-1 font-semibold text-primary-foreground">Use this</button>
            <button type="button" onClick={clear} className="rounded-lg border border-border px-3 py-1">Clear</button>
          </div>
        </div>,
        document.body,
      )}
    </span>
  );
}
