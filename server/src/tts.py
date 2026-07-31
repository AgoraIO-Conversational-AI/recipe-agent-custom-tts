"""OpenAI-compatible custom HTTP TTS endpoint used by this recipe."""

import asyncio
import math
import os
import struct
from typing import AsyncIterator, Optional

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

SAMPLE_RATE = 24000
CHUNK_DURATION_MS = 40
CHUNK_SIZE = SAMPLE_RATE * 2 * CHUNK_DURATION_MS // 1000

app = FastAPI(
    title="Custom HTTP TTS Server (Mock)",
    description="OpenAI-compatible HTTP TTS endpoint that streams raw PCM16 audio.",
    version="1.0.0",
)


class SpeechRequest(BaseModel):
    input: str
    app_id: Optional[str] = None
    model: Optional[str] = None
    voice: Optional[str] = None
    speed: Optional[float] = None
    sample_rate: int = SAMPLE_RATE
    response_format: str = "pcm"
    instruction: Optional[str] = None


def _validate_authorization(authorization: Optional[str]) -> None:
    expected_key = os.getenv("CUSTOM_TTS_API_KEY", "any-key-here")
    if authorization != f"Bearer {expected_key}":
        raise HTTPException(status_code=401, detail="Invalid custom TTS API key")


def _generate_tone(text: str) -> bytes:
    """Generate deterministic PCM16 audio for the mock endpoint."""
    duration = 2.0
    frequency = 360 + (sum(ord(character) for character in text) % 240)
    sample_count = int(SAMPLE_RATE * duration)
    fade_samples = int(SAMPLE_RATE * 0.03)
    audio = bytearray()

    for index in range(sample_count):
        envelope = min(
            1.0,
            index / fade_samples,
            (sample_count - index) / fade_samples,
        )
        value = int(
            12000
            * envelope
            * math.sin(2 * math.pi * frequency * index / SAMPLE_RATE)
        )
        audio.extend(struct.pack("<h", max(-32768, min(32767, value))))

    return bytes(audio)


async def _stream_chunks(audio: bytes) -> AsyncIterator[bytes]:
    for offset in range(0, len(audio), CHUNK_SIZE):
        yield audio[offset : offset + CHUNK_SIZE]
        await asyncio.sleep(CHUNK_DURATION_MS / 1000)


@app.post("/v1/audio/speech")
async def create_speech(
    request: SpeechRequest,
    authorization: Optional[str] = Header(None, alias="Authorization"),
):
    """Accept text and stream raw little-endian PCM16 mono audio."""
    _validate_authorization(authorization)
    if not request.input.strip():
        raise HTTPException(status_code=400, detail="input must not be empty")
    if request.response_format.lower() != "pcm":
        raise HTTPException(status_code=400, detail="response_format must be pcm")
    if request.sample_rate != SAMPLE_RATE:
        raise HTTPException(status_code=400, detail=f"sample_rate must be {SAMPLE_RATE}")

    return StreamingResponse(
        _stream_chunks(_generate_tone(request.input)),
        media_type="application/octet-stream",
        headers={"X-Audio-Sample-Rate": str(SAMPLE_RATE)},
    )


@app.get("/health")
async def health():
    return {"status": "ok", "service": "custom-http-tts-mock"}
