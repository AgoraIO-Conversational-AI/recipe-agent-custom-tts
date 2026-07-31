import { existsSync } from 'node:fs'
import path from 'node:path'

type BunRuntime = typeof globalThis & {
  Bun: {
    sleep: (ms: number) => Promise<void>
    spawn: (options: {
      cmd: string[]
      cwd: string
      env: Record<string, string | undefined>
      stdout: 'ignore'
      stderr: 'pipe'
    }) => {
      kill: () => void
      exited: Promise<number>
      exitCode: number | null
      stderr: ReadableStream<Uint8Array> | null
    }
    spawnSync: (options: {
      cmd: string[]
      cwd: string
      stderr: 'pipe'
      stdout: 'ignore'
    }) => {
      exitCode: number
      stderr: { toString: () => string }
    }
  }
}

const bunRuntime = globalThis as BunRuntime

function assert(condition: unknown, message: string): asserts condition {
  if (!condition) throw new Error(message)
}

async function waitForHealthy(baseUrl: string, timeoutMs: number) {
  const deadline = Date.now() + timeoutMs
  let lastError = 'backend did not start'

  while (Date.now() < deadline) {
    try {
      const response = await fetch(`${baseUrl}/tts/health`)
      if (response.ok) return
      lastError = `health returned ${response.status}`
    } catch (error) {
      lastError = error instanceof Error ? error.message : String(error)
    }
    await bunRuntime.Bun.sleep(250)
  }

  throw new Error(`Timed out waiting for mounted TTS endpoint: ${lastError}`)
}

async function main() {
  const projectRoot = process.cwd()
  const serverRoot = path.resolve(projectRoot, '..', 'server')
  const venvPython = path.join(serverRoot, 'venv', 'bin', 'python')

  if (!existsSync(venvPython)) {
    throw new Error('Missing server/venv/bin/python. Run bun run setup before verify:local:tts.')
  }

  const dependencyCheck = bunRuntime.Bun.spawnSync({
    cmd: [venvPython, '-c', 'import dotenv, fastapi, uvicorn, agora_agent'],
    cwd: serverRoot,
    stderr: 'pipe',
    stdout: 'ignore',
  })
  if (dependencyCheck.exitCode !== 0) {
    const stderr = dependencyCheck.stderr.toString().trim()
    throw new Error(
      `The backend virtualenv is missing required packages. Run bun run setup.${stderr ? ` Python said: ${stderr}` : ''}`,
    )
  }

  const port = 43160 + Math.floor(Math.random() * 20)
  const baseUrl = `http://127.0.0.1:${port}`
  const serverProcess = bunRuntime.Bun.spawn({
    cmd: [venvPython, 'scripts/run_fake_server.py'],
    cwd: serverRoot,
    env: {
      ...process.env,
      AGORA_APP_ID: '0123456789abcdef0123456789abcdef',
      AGORA_APP_CERTIFICATE: 'fedcba9876543210fedcba9876543210',
      CUSTOM_TTS_URL: 'https://example.ngrok-free.dev/tts/v1/audio/speech',
      CUSTOM_TTS_API_KEY: 'test-key',
      PORT: String(port),
    },
    stdout: 'ignore',
    stderr: 'pipe',
  })

  try {
    await waitForHealthy(baseUrl, 10_000)

    const response = await fetch(`${baseUrl}/tts/v1/audio/speech`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: 'Bearer test-key',
      },
      body: JSON.stringify({
        input: 'Hello from the custom TTS endpoint.',
        app_id: 'test-app-id',
        model: 'mock-tts',
        voice: 'mock-voice',
        speed: 1,
        sample_rate: 24000,
        response_format: 'pcm',
        instruction:
          'Please use standard American English, natural tone, moderate pace, and steady intonation',
      }),
    })

    assert(response.status === 200, 'POST /tts/v1/audio/speech should return 200')
    assert(
      (response.headers.get('content-type') ?? '').includes('application/octet-stream'),
      'The custom TTS endpoint should return an application/octet-stream response',
    )
    const audio = new Uint8Array(await response.arrayBuffer())
    assert(audio.length > 0, 'The custom TTS endpoint should return PCM audio bytes')
    assert(audio.length % 2 === 0, 'PCM16 output should contain complete two-byte samples')

    const unauthorized = await fetch(`${baseUrl}/tts/v1/audio/speech`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: 'Bearer wrong-key',
      },
      body: JSON.stringify({ input: 'Hello', response_format: 'pcm' }),
    })
    assert(unauthorized.status === 401, 'The custom TTS endpoint should reject an invalid key')

    console.log('Mounted custom TTS endpoint contract check passed')
  } finally {
    serverProcess.kill()
    await serverProcess.exited

    if (serverProcess.exitCode && serverProcess.exitCode !== 0) {
      const stderr = await new Response(serverProcess.stderr).text()
      if (stderr.trim()) console.error(stderr.trim())
    }
  }
}

await main()
