# Agora Agent Backend - Custom TTS Recipe

This FastAPI service owns Agora token generation and agent session lifecycle. It
also mounts the OpenAI-compatible custom TTS endpoint at `/tts`, so one process
serves both the browser-facing agent API and `POST /tts/v1/audio/speech`.

Agora cloud calls the TTS endpoint directly. For local development the backend
must therefore be exposed with a public tunnel such as `ngrok http 8000`. This
also makes the unauthenticated recipe endpoints public; add application auth and
rate limiting before deployment.

## Pipeline

`DeepgramSTT(nova-3, en)` -> `OpenAI(gpt-4o-mini)` ->
`GenericTTS(CUSTOM_TTS_URL)`

`src/tts.py` is a provider-free mock that turns each input string into raw PCM16
tone audio. Replace its synthesis function or point `CUSTOM_TTS_URL` to your own
compatible service.

## Run

Use the repository root README for the complete flow. To start only this module:

```bash
cd server
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python src/server.py
```

## Environment

Copy `.env.example` to `.env.local`. Required values:

- `AGORA_APP_ID` and `AGORA_APP_CERTIFICATE`
- `CUSTOM_TTS_URL`, a public HTTP(S) URL ending in `/tts/v1/audio/speech`
- `CUSTOM_TTS_API_KEY`, forwarded as `Authorization: Bearer <key>`
- `CUSTOM_TTS_APP_ID`, forwarded to the custom TTS endpoint as `app_id`

Optional values: `CUSTOM_TTS_MODEL` (`mock-tts`), `CUSTOM_TTS_VOICE` (`mock-voice`),
`AGENT_GREETING`, and `PORT` (`8000`).

The dependency file installs `agora-agents` from PyPI. A narrow adapter in
`src/agent.py` maps the published SDK's `GenericTTS` configuration to the cloud
`generic_http` vendor name.

## API

- `GET /get_config` - token and channel/UID config
- `POST /startAgent` - start an agent session
- `POST /stopAgent` - stop an agent session
- `POST /tts/v1/audio/speech` - synthesize raw PCM audio
- `GET /tts/health` - custom TTS endpoint health

The TTS request is OpenAI-compatible JSON with `input`, `app_id`, `instruction`,
`model`, `voice`, `speed`, `sample_rate`, and `response_format`. This mock
supports raw PCM16 at 24 kHz.

`bun run verify:local:fastapi` tests the lifecycle routes with a fake agent.
`bun run verify:local:tts` tests the mounted TTS endpoint. `pytest tests` covers
the SDK serialization, endpoint contract, authentication, and import boundary;
none of these tests starts a live Agora session.
