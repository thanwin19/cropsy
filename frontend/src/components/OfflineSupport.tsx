import { useEffect, useState } from "react";

/** Registers the service worker (production builds only) and shows a small banner when the network is gone. */
export function OfflineSupport() {
  const [online, setOnline] = useState(true);
  useEffect(() => {
    setOnline(navigator.onLine);
    const on = () => setOnline(true);
    const off = () => setOnline(false);
    window.addEventListener("online", on);
    window.addEventListener("offline", off);
    if (import.meta.env.PROD && "serviceWorker" in navigator) {
      navigator.serviceWorker.register("/sw.js").catch(() => undefined);
    }
    return () => {
      window.removeEventListener("online", on);
      window.removeEventListener("offline", off);
    };
  }, []);
  if (online) return null;
  return (
    <div role="status" className="fixed inset-x-0 top-0 z-[100] bg-amber-600 px-3 py-1.5 text-center text-xs font-medium text-black">
      No internet. You can read your saved answers; new questions need a connection.
    </div>
  );
}
