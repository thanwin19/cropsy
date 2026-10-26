"""voice_api.py: voice questions. The browser streams 16 kHz mono audio over a WebSocket; this relays it to Amazon Transcribe streaming (Mumbai) and sends back the text.
The text goes into the question box for the farmer to check before sending, so a mis-heard word never triggers an answer by itself.
Cost guard: each clip is cut at CROPSY_VOICE_SECONDS (default 20) and the number of clips per server run is capped (CROPSY_VOICE_MAX, default 60)."""
from __future__ import annotations

import asyncio
import json
import os

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app import config

router = APIRouter()
MAX_SECONDS = int(os.getenv("CROPSY_VOICE_SECONDS", "20"))
CAP = int(os.getenv("CROPSY_VOICE_MAX", "60"))
LANGS = {"ta-IN", "en-IN", "hi-IN"}
_used = {"n": 0}


def _resolver():
    from amazon_transcribe.auth import StaticCredentialResolver
    from app import aws_resources
    c = aws_resources.session().get_credentials().get_frozen_credentials()
    return StaticCredentialResolver(access_key_id=c.access_key, secret_access_key=c.secret_key, session_token=c.token)


@router.websocket("/api/voice/stream")
async def stream(ws: WebSocket, lang: str = "ta-IN"):
    await ws.accept()
    if lang not in LANGS:
        lang = "ta-IN"
    if _used["n"] >= CAP:
        await ws.send_json({"error": f"Voice limit ({CAP} clips per run) reached, to protect AWS credit. Please type the question."})
        await ws.close()
        return
    _used["n"] += 1
    try:
        from amazon_transcribe.client import TranscribeStreamingClient
        client = TranscribeStreamingClient(region=config.AWS_REGION if hasattr(config, "AWS_REGION") else "ap-south-1", credential_resolver=_resolver())
        st = await client.start_stream_transcription(language_code=lang, media_sample_rate_hz=16000, media_encoding="pcm")
    except Exception as e:  # noqa: BLE001
        await ws.send_json({"error": f"Voice service unavailable: {str(e)[:120]}"})
        await ws.close()
        return

    async def up():
        sent = 0
        try:
            while sent < MAX_SECONDS * 32000:
                msg = await ws.receive()
                if msg.get("bytes"):
                    sent += len(msg["bytes"])
                    await st.input_stream.send_audio_event(audio_chunk=msg["bytes"])
                elif msg.get("text") == "end" or msg.get("type") == "websocket.disconnect":
                    break
        finally:
            await st.input_stream.end_stream()

    async def down():
        async for ev in st.output_stream:
            for r in getattr(ev, "transcript", None).results if getattr(ev, "transcript", None) else []:
                if r.alternatives:
                    await ws.send_json({"final" if not r.is_partial else "partial": r.alternatives[0].transcript})

    try:
        await asyncio.gather(up(), down())
        await ws.send_json({"done": True, "language": lang, "note": "Transcribed by Amazon Transcribe. Check the words before sending."})
    except (WebSocketDisconnect, RuntimeError):
        pass
    except Exception as e:  # noqa: BLE001
        try:
            await ws.send_json({"error": f"Voice failed: {str(e)[:120]}"})
        except Exception:  # noqa: BLE001
            pass
    try:
        await ws.close()
    except Exception:  # noqa: BLE001
        pass
