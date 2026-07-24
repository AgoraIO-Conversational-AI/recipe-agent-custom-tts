# Architecture - Custom TTS Recipe

The application has a Next.js frontend and one FastAPI backend. The browser uses
Next.js `/api/*` rewrites for token and agent lifecycle calls. The backend also
serves the custom TTS endpoint, which Agora cloud calls through a public URL.

## Request flow

```text
Browser
  |  GET /api/get_config
  |  POST /api/startAgent
  v
Next.js (/api/* rewrite)
  v
FastAPI agent backend
  |  GenericTTS(url=CUSTOM_TTS_URL, api_key=CUSTOM_TTS_API_KEY)
  v
Agora ConvoAI Cloud
  |  user audio -> Deepgram STT -> OpenAI LLM -> response text
  |  POST <CUSTOM_TTS_URL>
  |    Authorization: Bearer <CUSTOM_TTS_API_KEY>
  |    JSON: input, app_id, instruction, model, voice, speed, sample_rate, response_format
  v
Custom TTS endpoint (mounted at /tts, public through a tunnel)
  |  raw little-endian PCM16 / 24 kHz / mono bytes
  v
Agora ConvoAI Cloud -> RTC audio + RTM transcript/metrics -> browser
```

`POST /api/stopAgent` ends the Agent session.

## One process, two surfaces

`server/src/server.py` mounts the provider-agnostic TTS app from
`server/src/tts.py` at `/tts`. This keeps the example easy to run with one public
tunnel while maintaining a one-way dependency: `server.py` imports `tts.py`, and
`tts.py` does not import `agora_agent`.

The public tunnel exposes both `/tts/*` and the agent lifecycle endpoints. The
recipe does not authenticate `/get_config`, `/startAgent`, or `/stopAgent`; a real
deployment must protect those routes with application auth and rate limiting.

## API

| Endpoint | Method | Description |
| --- | --- | --- |
| `/get_config` | GET | Generate token and channel/UID config |
| `/startAgent` | POST | Start an Agent session |
| `/stopAgent` | POST | Stop an Agent session |
| `/tts/v1/audio/speech` | POST | OpenAI-compatible custom TTS endpoint |
| `/tts/health` | GET | Custom TTS health check |

## Credentials

- Browser -> backend: none in this local recipe.
- Backend -> Agora cloud: `AGORA_APP_ID` + `AGORA_APP_CERTIFICATE`.
- Agora cloud -> custom TTS: `Authorization: Bearer <CUSTOM_TTS_API_KEY>`.

Credentials remain in `server/.env.local` and are never sent to the browser.

## Audio contract

The `GenericTTS` configuration fixes `sample_rate=24000` and
`response_format="pcm"`. The endpoint must return headerless signed 16-bit
little-endian mono samples. A WAV container, MP3 data, another sample rate, or
stereo output is incompatible with this recipe configuration.
