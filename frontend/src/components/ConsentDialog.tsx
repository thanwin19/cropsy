import { useEffect, useState } from "react";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { getConsent, setConsent, type Consent } from "@/lib/privacy";

/** First-run privacy notice with two separate choices. Photos are only analysed after the farmer says yes. */
export function ConsentDialog({ open, onClose, reason }: { open: boolean; onClose: (c: Consent) => void; reason?: string }) {
  const [photos, setPhotos] = useState(false);
  const [improve, setImprove] = useState(false);
  useEffect(() => {
    if (open) {
      const c = getConsent();
      setPhotos(c.photos);
      setImprove(c.improve);
    }
  }, [open]);
  const save = () => {
    const c = { decided: true, photos, improve };
    setConsent(c);
    onClose(c);
  };
  const box = "mt-0.5 size-4 shrink-0 accent-[var(--primary)]";
  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose(getConsent())}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Your data and Cropsy</DialogTitle>
          <DialogDescription>
            {reason ?? "Cropsy only uses what you type or attach. It does not collect your name, phone number or GPS location. Parcel records here are dummy data."}
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-3 text-sm">
          <label className="flex items-start gap-2">
            <input type="checkbox" className={box} checked={photos} onChange={(e) => setPhotos(e.target.checked)} />
            <span>
              <b>Let Cropsy look at photos I attach.</b> The photo goes to this server and to AWS Bedrock to be compared with reference photos. Only its file name is kept in the history.
            </span>
          </label>
          <label className="flex items-start gap-2">
            <input type="checkbox" className={box} checked={improve} onChange={(e) => setImprove(e.target.checked)} />
            <span>
              <b>Help improve Cropsy.</b> Save the text of questions Cropsy could not understand (no name, phone or location) so new guidance can be added.
            </span>
          </label>
          <p className="text-xs text-muted-foreground">You can change this, or delete your data, any time in Settings. Your chat history stays in this browser.</p>
        </div>
        <DialogFooter>
          <Button onClick={save}>Save my choices</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
