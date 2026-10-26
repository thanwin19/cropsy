import { getApiSettings } from "@/lib/cropsy-api";

export type VoiceLang = "ta-IN" | "en-IN";

/** Record from the microphone, stream 16 kHz mono audio to the backend (Amazon Transcribe), and report text as it arrives. Returns a stop() function. */
export async function startVoice(lang: VoiceLang, on: { partial: (t: string) => void; final: (t: string) => void; error: (m: string) => void; end: () => void }): Promise<() => void> {
  const stream = await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true } });
  const base = (getApiSettings().baseUrl || window.location.origin).replace(/\/$/, "").replace(/^http/, "ws");
  const ws = new WebSocket(`${base}/api/voice/stream?lang=${lang}`);
  ws.binaryType = "arraybuffer";
  const ctx = new AudioContext();
  if (ctx.state === "suspended") await ctx.resume();
  const src = ctx.createMediaStreamSource(stream);
  const proc = ctx.createScriptProcessor(4096, 1, 1);
  let open = false, stopped = false, finals: string[] = [];
  const cleanup = () => { try { proc.disconnect(); src.disconnect(); } catch { /* already closed */ } stream.getTracks().forEach((t) => t.stop()); void ctx.close(); };
  const stop = () => {
    if (stopped) return;
    stopped = true;
    cleanup();
    if (ws.readyState === WebSocket.OPEN) ws.send("end");
  };
  ws.onopen = () => { open = true; };
  ws.onmessage = (e) => {
    const m = JSON.parse(String(e.data));
    if (m.partial) on.partial([...finals, m.partial].join(" "));
    else if (m.final) { finals = [...finals, m.final]; on.final(finals.join(" ")); }
    else if (m.error) { on.error(m.error); stop(); }
    else if (m.done) on.end();
  };
  ws.onerror = () => { on.error("Could not reach the voice service. Please type the question."); stop(); };
  ws.onclose = () => { stop(); on.end(); };
  proc.onaudioprocess = (e) => {
    if (!open || ws.readyState !== WebSocket.OPEN) return;
    const input = e.inputBuffer.getChannelData(0), ratio = ctx.sampleRate / 16000;
    const out = new Int16Array(Math.floor(input.length / ratio));
    for (let i = 0; i < out.length; i++) out[i] = Math.max(-1, Math.min(1, input[Math.floor(i * ratio)])) * 0x7fff;
    ws.send(out.buffer);
  };
  src.connect(proc);
  proc.connect(ctx.destination);
  setTimeout(stop, 20000);
  return stop;
}
