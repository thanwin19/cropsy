"""voice_probe.py: send a spoken test clip through the voice WebSocket and print what comes back. Usage: python scripts/voice_probe.py [ws://localhost:8000] [wav]"""
import asyncio, sys, wave, json
import websockets

async def main(base: str, wav: str, lang: str):
    w = wave.open(wav); pcm = w.readframes(w.getnframes())
    async with websockets.connect(f"{base}/api/voice/stream?lang={lang}") as ws:
        for i in range(0, len(pcm), 3200):
            await ws.send(pcm[i:i + 3200]); await asyncio.sleep(0.02)
        await ws.send("end")
        async for m in ws:
            print(json.loads(m))

base = sys.argv[1] if len(sys.argv) > 1 else "ws://localhost:8000"
wav = sys.argv[2] if len(sys.argv) > 2 else "C:/Users/ELCOT/AppData/Local/Temp/q.wav"
asyncio.run(main(base, wav, "en-IN"))
