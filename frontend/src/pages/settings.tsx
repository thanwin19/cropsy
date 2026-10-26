import { useEffect, useState } from 'react';
import { Check, ExternalLink, Info, RotateCcw, Save, Server, Wifi } from 'lucide-react';
import { CropsyShell, SectionLabel } from '@/components/cropsy-shell';
import { checkApiHealth, getApiSettings, saveApiSettings } from '@/lib/cropsy-api';
import { deleteMyData, getConsent, setConsent, type Consent } from '@/lib/privacy';

export function ConnectionSettings({ stacked = false }: { stacked?: boolean }) {
  // Saved values live in localStorage, so they are read after mount (the server render has none).
  const [baseUrl, setBaseUrl] = useState('');
  const [demoMode, setDemoMode] = useState(false);
  useEffect(() => {
    const initial = getApiSettings();
    setBaseUrl(initial.baseUrl);
    setDemoMode(initial.demoMode);
  }, []);
  const [saved, setSaved] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState('');
  function save() { saveApiSettings({ baseUrl: baseUrl.trim(), demoMode }); setSaved(true); setTimeout(() => setSaved(false), 2200); }
  async function testConnection() {
    setTesting(true); setTestResult('');
    try {
      const result = await checkApiHealth({ baseUrl: baseUrl.trim(), demoMode });
      setTestResult(demoMode ? 'Demo adapter is ready.' : `Connected · ${result.status}`);
    } catch (error) {
      setTestResult(error instanceof Error ? error.message : 'Could not reach the backend.');
    } finally {
      setTesting(false);
    }
  }
  return (
    <div className={stacked ? "grid gap-4" : "mt-9 grid gap-5 lg:grid-cols-[1fr_300px]"}><section className="rounded-2xl border border-border bg-card p-5 shadow-[var(--shadow-sm)] md:p-7"><div className="flex items-start gap-3 border-b border-border pb-5"><span className="grid size-9 place-items-center rounded-xl bg-primary/10 text-primary"><Server size={17} /></span><div><h2 className="text-[14px] font-extrabold">Backend connection</h2><p className="mt-1 text-[11px] text-muted-foreground">The adapter follows Cropsy's query, execution, and SSE contracts.</p></div></div><label className="mt-6 block"><span className="mono text-[10px] uppercase tracking-[.12em] text-muted-foreground">API base URL</span><input value={baseUrl} onChange={(event) => setBaseUrl(event.target.value)} placeholder="https://api.example.com" className="focus-ring mt-2 h-11 w-full rounded-xl border border-input bg-background px-3 text-[12px] outline-none" data-testid="input-api-base-url" /><span className="mt-2 block text-[10px] text-muted-foreground">Defaults to <span className="mono">VITE_CROPSY_API_BASE</span> at build time.</span></label><div className="mt-6 flex items-center justify-between rounded-xl border border-border bg-secondary/45 p-4"><div className="flex items-start gap-3"><span className="mt-0.5 text-primary"><Wifi size={16} /></span><div><p className="text-[12px] font-bold">Demo mode</p><p className="mt-1 max-w-[360px] text-[10px] leading-relaxed text-muted-foreground">Use a realistic local trace with parcel records, model routing, citations, and a flagged crop signal. No backend required.</p></div></div><button onClick={() => setDemoMode(!demoMode)} role="switch" aria-checked={demoMode} className={`focus-ring relative h-6 w-11 shrink-0 rounded-full transition-colors ${demoMode ? 'bg-primary' : 'bg-border'}`} data-testid="switch-demo-mode"><span className={`absolute top-1 size-4 rounded-full bg-card shadow-sm transition-transform ${demoMode ? 'translate-x-6' : 'translate-x-1'}`} /></button></div><div className="mt-6 flex flex-wrap items-center gap-3"><button onClick={save} className="focus-ring inline-flex items-center gap-2 rounded-xl bg-primary px-4 py-3 text-[11px] font-bold text-primary-foreground" data-testid="button-save-settings">{saved ? <Check size={14} /> : <Save size={14} />}{saved ? 'Saved' : 'Save settings'}</button><button onClick={testConnection} disabled={testing} className="focus-ring inline-flex items-center gap-2 rounded-xl border border-border bg-background px-4 py-3 text-[11px] font-bold disabled:opacity-50" data-testid="button-test-connection">{testing ? <span className="size-3 animate-pulse rounded-full bg-primary" /> : <RotateCcw size={14} />}{testing ? 'Testing…' : 'Test connection'}</button>{testResult && <span className="text-[10px] text-primary">{testResult}</span>}</div></section>
      <aside className="space-y-4"><div className={`rounded-2xl border p-5 ${demoMode ? 'border-accent/35 bg-accent/[.08]' : 'border-border bg-card'}`}><div className="flex items-center gap-2">{demoMode ? <Info size={16} className="text-accent" /> : <Wifi size={16} className="text-primary" />}<span className="text-[12px] font-extrabold">{demoMode ? 'Demo flow active' : 'Live backend active'}</span></div><p className="mt-3 text-[11px] leading-relaxed text-muted-foreground">{demoMode ? 'Queries resolve locally so your team can explore the full trace experience before connecting a backend.' : 'Queries will use the configured backend and stream task updates over EventSource.'}</p></div><div className="rounded-2xl border border-border bg-card p-5"><SectionLabel>Contract surface</SectionLabel><div className="mt-4 space-y-3">{['POST /query · multipart', 'GET /execution/{id}', 'SSE /execution/{id}/stream'].map((line) => <div key={line} className="flex items-center gap-2 text-[10px]"><Check size={13} className="text-primary" /><span className="mono">{line}</span></div>)}</div><a href="#" onClick={(event) => event.preventDefault()} className="focus-ring mt-5 inline-flex items-center gap-1 text-[10px] font-bold text-primary hover:underline" data-testid="link-api-contract">View adapter contract <ExternalLink size={12} /></a></div></aside>
    </div>
  );
}

export function PrivacyPanel() {
  const [c, setC] = useState<Consent>({ decided: false, photos: false, improve: false });
  const [msg, setMsg] = useState('');
  useEffect(() => setC(getConsent()), []);
  const update = (patch: Partial<Consent>) => {
    const next = { ...c, ...patch, decided: true };
    setC(next);
    setConsent(next);
  };
  async function wipe() {
    if (!window.confirm('Delete the saved history, uploaded files and unclear-question log from the server, and everything Cropsy keeps in this browser?')) return;
    const ok = await deleteMyData(getApiSettings().baseUrl);
    setMsg(ok ? 'Deleted. Your choices were reset too.' : 'Browser data cleared; the server could not be reached to clear its copy.');
    setC({ decided: false, photos: false, improve: false });
  }
  return (
    <section className="mt-5 rounded-2xl border border-border bg-card p-5 md:p-7" data-testid="privacy-panel">
      <h2 className="text-[14px] font-extrabold">Privacy and consent</h2>
      <p className="mt-1 max-w-[560px] text-[11px] leading-relaxed text-muted-foreground">
        Cropsy uses only what you type or attach. It does not collect your name, phone number or GPS location. Parcel records in this demo are dummy data. Chat history stays in this browser.
      </p>
      <label className="mt-4 flex items-start gap-3 text-[12px]">
        <input type="checkbox" className="mt-0.5 size-4 accent-[var(--primary)]" checked={c.photos} onChange={(e) => update({ photos: e.target.checked })} />
        <span><b>Let Cropsy look at photos I attach.</b> They go to this server and AWS Bedrock to be compared with reference photos; only the file name is kept.</span>
      </label>
      <label className="mt-3 flex items-start gap-3 text-[12px]">
        <input type="checkbox" className="mt-0.5 size-4 accent-[var(--primary)]" checked={c.improve} onChange={(e) => update({ improve: e.target.checked })} />
        <span><b>Help improve Cropsy.</b> Save the text of questions Cropsy could not understand, with no personal details.</span>
      </label>
      <div className="mt-5 flex flex-wrap items-center gap-3">
        <button onClick={wipe} className="focus-ring rounded-xl border border-destructive/50 px-4 py-2.5 text-[11px] font-bold text-destructive hover:bg-destructive/10" data-testid="button-delete-data">Delete my data</button>
        {msg && <span className="text-[11px] text-muted-foreground">{msg}</span>}
      </div>
    </section>
  );
}

export default function Settings() {
  return <CropsyShell><div className="mx-auto max-w-[980px] px-5 py-8 md:px-10 md:py-11"><div><SectionLabel>System / connection behavior</SectionLabel><h1 className="serif mt-2 text-[39px] leading-none tracking-[-.035em]">Settings</h1><p className="mt-3 max-w-[520px] text-[13px] leading-relaxed text-muted-foreground">Choose where traces run and how Cropsy should behave when the field network is unreliable.</p></div>
    <ConnectionSettings />
    <PrivacyPanel />
  </div></CropsyShell>;
}
