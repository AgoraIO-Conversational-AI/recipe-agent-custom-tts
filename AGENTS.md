# Agent Development Guide

This repository is the custom HTTP TTS recipe in the Agora Conversational AI
recipes family. It follows the Python FastAPI + Next.js structure used by the
other recipes.

## System shape

- `server/` owns Agora tokens, Agent lifecycle, and the mounted `/tts` endpoint.
- `server/src/agent.py` builds Deepgram STT -> OpenAI LLM -> `GenericTTS`.
- `server/src/tts.py` implements the provider-agnostic mock HTTP TTS endpoint.
- `web/` owns RTC/RTM lifecycle and the conversation UI; `/api/*` are Next.js
  rewrites to the backend.
- Server credentials stay in `server/.env.local` and must never enter `web/`.

## Invariants

- `CUSTOM_TTS_URL` must be a public HTTP(S) endpoint; Agora cloud cannot call
  localhost.
- `CUSTOM_TTS_API_KEY` must be non-empty and matches the endpoint Bearer token.
- The endpoint returns raw PCM16 little-endian, 24 kHz, mono audio without a WAV
  header.
- Keep `server/src/tts.py` independent of `agora-agents`; a test enforces this.
- Keep the Next.js `/api/*` rewrites and the existing lifecycle response shapes.
- Do not put `PORT` in `server/.env.example`; dotenv override would replace the
  random port used by local verification.

## Commands

```bash
bun run setup
bun run dev
bun run doctor
bun run doctor:local
bun run verify
bun run verify:local
```

## Done criteria

1. Run the narrowest relevant verification command.
2. Web changes: `bun run verify:web` passes.
3. Backend changes: `bun run verify:local` or the relevant narrower checks pass.
4. Env or setup changes update the root README, `server/README.md`, and
   `server/.env.example` together.

## Git conventions

- Use Conventional Commits (`feat`, `fix`, `chore`, `test`, `docs`).
- Keep the subject lowercase and in present tense.
- Do not add AI tool names, `Co-Authored-By`, or `--no-verify`.
- Use `type/short-description` branch names.
