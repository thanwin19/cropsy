import { useEffect, useState, type ReactNode } from "react";
import { Link, useNavigate, useRouterState } from "@tanstack/react-router";
import { Activity, Bell, BotMessageSquare, ExternalLink, Leaf, Map, RefreshCw, Settings, ShieldAlert, ShieldCheck, Sprout } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { ErrorBoundary } from "@/components/error-boundary";
import { PrintReport } from "@/components/stitch/PrintReport";
import { fetchAlerts, type AlertsResponse, type FieldAlert } from "@/lib/cropsy-api";
import { ConnectionSettings } from "../../pages/settings";
import { SampleTag, StatusChip } from "./ui";
import { useCropsy } from "./store";

const nav = [
  { to: "/", label: "Ask", hint: "Chat and solar map", icon: BotMessageSquare },
  { to: "/field", label: "My field", hint: "Advisory, water, soil, history", icon: Sprout },
  { to: "/satellite", label: "Satellite", hint: "16 layers and index results", icon: Map },
  { to: "/trust", label: "Trust", hint: "Sources and route trace", icon: ShieldCheck },
] as const;

const SEV_TONE = { high: "bad", medium: "warn", low: "default" } as const;
type AlertFilter = "all" | "crop_stress" | "heavy_rain" | "irrigation_due" | "recorded_issue";
const FILTERS: AlertFilter[] = ["all", "crop_stress", "heavy_rain", "irrigation_due", "recorded_issue"];

/** Village-wide early-stress alerts from the backend (/api/alerts), newest and most severe first. */
function AlertsSheet({ open, onOpenChange }: { open: boolean; onOpenChange: (v: boolean) => void }) {
  const navigate = useNavigate();
  const { selectParcel } = useCropsy();
  const [data, setData] = useState<AlertsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<AlertFilter>("all");
  const [loading, setLoading] = useState(false);

  const load = () => {
    setLoading(true);
    setError(null);
    fetchAlerts("low")
      .then(setData)
      .catch((e) => setError(e?.message || "Could not load alerts"))
      .finally(() => setLoading(false));
  };
  useEffect(() => {
    if (open && !data) load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const shown = (data?.alerts || []).filter((a) => filter === "all" || a.type === filter).slice(0, 80);
  const askAbout = (a: FieldAlert) => {
    onOpenChange(false);
    void navigate({ to: "/", search: { parcel: a.parcel_id } });
  };
  const openReport = (a: FieldAlert) => {
    onOpenChange(false);
    selectParcel(a.parcel_id);
    void navigate({ to: "/field" });
  };

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="flex w-full flex-col gap-0 sm:max-w-md">
        <SheetHeader>
          <SheetTitle>Early-stress alerts</SheetTitle>
          <SheetDescription>
            {data ? `${data.count} alerts across all fields · forecast: ${data.forecast_source}` : "Satellite, weather and recorded-issue alerts for every field."}
          </SheetDescription>
        </SheetHeader>
        <div className="flex flex-wrap items-center gap-1.5 px-4">
          {FILTERS.map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`rounded-full border px-2.5 py-0.5 font-mono text-[11px] ${filter === f ? "border-primary bg-primary/10 text-primary" : "border-border text-muted-foreground hover:text-foreground"}`}
            >
              {f === "all" ? `All ${data?.count ?? ""}`.trim() : `${f.replace(/_/g, " ")} ${data?.by_type[f] ?? 0}`}
            </button>
          ))}
          <Button size="icon" variant="ghost" aria-label="Refresh alerts" className="ml-auto size-8" onClick={load} disabled={loading}>
            <RefreshCw className={loading ? "animate-spin" : ""} />
          </Button>
        </div>
        <div className="mt-3 min-h-0 flex-1 space-y-3 overflow-y-auto px-4 pb-4">
          {error && <p className="rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-xs text-destructive">{error}. Start the backend (port 8000).</p>}
          {!data && !error && <p className="text-xs text-muted-foreground">Loading alerts…</p>}
          {shown.map((a, i) => (
            <div key={`${a.parcel_id}-${a.type}-${i}`} className="rounded-xl border border-border p-4">
              <div className="flex items-center justify-between gap-2">
                <b className="font-mono">{a.parcel_id}</b>
                <StatusChip tone={SEV_TONE[a.severity]}>{a.severity}</StatusChip>
              </div>
              <p className="mt-2 text-sm font-medium">{a.title}</p>
              <p className="mt-1 text-xs leading-relaxed text-muted-foreground">{a.detail}</p>
              <p className="mt-2 text-xs">{a.action}</p>
              <p className="mt-2 font-mono text-[10px] text-muted-foreground">basis: {a.basis}</p>
              <div className="mt-3 flex items-center justify-between gap-2">
                {a.type === "recorded_issue" ? <SampleTag kind="dummy record" /> : <SampleTag kind="live signal" />}
                <div className="flex gap-2">
                  <Button size="sm" variant="outline" onClick={() => openReport(a)}>Field report</Button>
                  <Button size="sm" onClick={() => askAbout(a)}>Ask about this</Button>
                </div>
              </div>
            </div>
          ))}
          {data && shown.length === 0 && <p className="text-xs text-muted-foreground">No alerts in this group.</p>}
        </div>
        <div className="flex items-center justify-between gap-2 border-t border-border px-4 py-3 text-xs">
          <Link to="/flagged" onClick={() => onOpenChange(false)} className="inline-flex items-center gap-1.5 text-muted-foreground hover:text-foreground">
            <ShieldAlert className="size-4" /> Flagged cases
          </Link>
          <Link to="/runs" onClick={() => onOpenChange(false)} className="inline-flex items-center gap-1.5 text-muted-foreground hover:text-foreground">
            <Activity className="size-4" /> Execution runs
          </Link>
        </div>
      </SheetContent>
    </Sheet>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const [alertsOpen, setAlertsOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const { alertCount, printReport, closePrint } = useCropsy();
  const pathname = useRouterState({ select: (s) => s.location.pathname });

  return (
    <TooltipProvider>
      <div className="min-h-screen bg-background text-foreground md:grid md:grid-cols-[76px_minmax(0,1fr)]">
        <aside className="fixed inset-y-0 left-0 z-40 hidden w-[76px] flex-col items-center border-r border-border bg-sidebar py-4 md:flex">
          <Link to="/" aria-label="Cropsy home" className="grid size-11 place-items-center rounded-xl bg-primary text-primary-foreground">
            <Leaf className="size-5" />
          </Link>
          <div className="mt-2 text-center">
            <p className="text-[11px] font-semibold">Cropsy</p>
            <p className="font-mono text-[8px] text-muted-foreground">Then Malai</p>
          </div>
          <nav className="mt-8 flex flex-1 flex-col gap-2">
            {nav.map(({ to, label, hint, icon: Icon }) => (
              <Tooltip key={to}>
                <TooltipTrigger asChild>
                  <Link
                    to={to}
                    aria-label={`${label}: ${hint}`}
                    className="grid size-11 place-items-center rounded-lg text-muted-foreground transition hover:bg-accent hover:text-foreground"
                    activeProps={{ className: "grid size-11 place-items-center rounded-lg bg-primary text-primary-foreground" }}
                    activeOptions={{ exact: to === "/" }}
                  >
                    <Icon className="size-5" />
                  </Link>
                </TooltipTrigger>
                <TooltipContent side="right">
                  <b>{label}</b> · {hint}
                </TooltipContent>
              </Tooltip>
            ))}
          </nav>
          <div className="space-y-2">
            <Tooltip>
              <TooltipTrigger asChild>
                <Button size="icon" variant="ghost" aria-label={alertCount ? `${alertCount} high-priority alerts` : "Alerts"} className="relative min-h-11 min-w-11" onClick={() => setAlertsOpen(true)}>
                  <Bell />
                  {alertCount > 0 && (
                    <span className="absolute right-1 top-1 grid h-4 min-w-4 place-items-center rounded-full bg-destructive px-1 font-mono text-[9px] text-destructive-foreground">{alertCount}</span>
                  )}
                </Button>
              </TooltipTrigger>
              <TooltipContent side="right">{alertCount ? `${alertCount} high-priority alerts` : "Alerts"}</TooltipContent>
            </Tooltip>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button size="icon" variant="ghost" aria-label="Settings" className="min-h-11 min-w-11" onClick={() => setSettingsOpen(true)}>
                  <Settings />
                </Button>
              </TooltipTrigger>
              <TooltipContent side="right">Settings</TooltipContent>
            </Tooltip>
          </div>
        </aside>

        <main className="min-w-0 pb-16 md:col-start-2 md:pb-0">
          {/* a crash on one page keeps the rail and tab bar alive, and clears when you move to another page */}
          <ErrorBoundary resetKey={pathname}>{children}</ErrorBoundary>
        </main>

        <nav className="fixed inset-x-0 bottom-0 z-50 grid grid-cols-6 border-t border-border bg-sidebar/95 backdrop-blur-xl md:hidden">
          {nav.map(({ to, label, icon: Icon }) => (
            <Link
              key={to}
              to={to}
              className="flex min-h-16 flex-col items-center justify-center gap-1 text-[10px] text-muted-foreground"
              activeProps={{ className: "flex min-h-16 flex-col items-center justify-center gap-1 text-[10px] text-primary" }}
              activeOptions={{ exact: to === "/" }}
            >
              <Icon className="size-5" />
              <span>{label}</span>
            </Link>
          ))}
          <button
            type="button"
            aria-label={alertCount ? `${alertCount} high-priority alerts` : "Alerts"}
            onClick={() => setAlertsOpen(true)}
            className="relative flex min-h-16 flex-col items-center justify-center gap-1 text-[10px] text-muted-foreground"
          >
            <Bell className="size-5" />
            <span>Alerts</span>
            {alertCount > 0 && <span className="absolute right-4 top-2 grid h-4 min-w-4 place-items-center rounded-full bg-destructive px-1 font-mono text-[9px] text-destructive-foreground">{alertCount}</span>}
          </button>
          <button type="button" aria-label="Settings" onClick={() => setSettingsOpen(true)} className="flex min-h-16 flex-col items-center justify-center gap-1 text-[10px] text-muted-foreground">
            <Settings className="size-5" />
            <span>Settings</span>
          </button>
        </nav>

        <AlertsSheet open={alertsOpen} onOpenChange={setAlertsOpen} />

        <Sheet open={settingsOpen} onOpenChange={setSettingsOpen}>
          <SheetContent className="w-full overflow-y-auto sm:max-w-md">
            <SheetHeader>
              <SheetTitle>Settings</SheetTitle>
              <SheetDescription>Where Cropsy gets its answers, and how it behaves when the field network is unreliable.</SheetDescription>
            </SheetHeader>
            <div className="mt-4 space-y-4 px-4 pb-6">
              <ConnectionSettings stacked />
              <div className="rounded-xl border border-border p-4">
                <p className="text-sm font-medium">Theme</p>
                <p className="mt-1 text-xs text-muted-foreground">Dark default · light tokens included</p>
              </div>
              <div className="grid gap-2 sm:grid-cols-2">
                <Button asChild variant="outline" size="sm" onClick={() => setSettingsOpen(false)}>
                  <Link to="/flagged"><ShieldAlert />Flagged cases</Link>
                </Button>
                <Button asChild variant="outline" size="sm" onClick={() => setSettingsOpen(false)}>
                  <Link to="/runs"><Activity />Execution runs</Link>
                </Button>
              </div>
              <Button asChild variant="ghost" size="sm" className="w-full" onClick={() => setSettingsOpen(false)}>
                <Link to="/settings"><ExternalLink />Open the full settings page</Link>
              </Button>
            </div>
          </SheetContent>
        </Sheet>

        {printReport && <PrintReport report={printReport} onClose={closePrint} />}
      </div>
    </TooltipProvider>
  );
}
