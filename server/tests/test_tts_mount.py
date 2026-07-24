"""The custom HTTP TTS endpoint is mounted and remains provider-agnostic."""


def test_tts_health_is_mounted(client):
    response = client.get("/tts/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "custom-http-tts-mock"}


def test_tts_speech_endpoint_streams_pcm(client, monkeypatch):
    async def no_sleep(_seconds):
        return None

    monkeypatch.setattr("tts.asyncio.sleep", no_sleep)
    response = client.post(
        "/tts/v1/audio/speech",
        headers={"Authorization": "Bearer test-key"},
        json={
            "input": "Hello from the custom TTS endpoint.",
            "app_id": "test-app-id",
            "model": "mock-tts",
            "voice": "mock-voice",
            "speed": 1,
            "sample_rate": 24000,
            "response_format": "pcm",
            "instruction": (
                "Please use standard American English, natural tone, "
                "moderate pace, and steady intonation"
            ),
        },
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/octet-stream")
    assert response.headers["x-audio-sample-rate"] == "24000"
    assert len(response.content) == 24000 * 2 * 2
    assert len(response.content) % 2 == 0


def test_tts_speech_endpoint_rejects_invalid_key(client):
    response = client.post(
        "/tts/v1/audio/speech",
        headers={"Authorization": "Bearer wrong-key"},
        json={"input": "Hello", "response_format": "pcm"},
    )
    assert response.status_code == 401


def test_tts_speech_endpoint_rejects_incompatible_audio_format(client):
    response = client.post(
        "/tts/v1/audio/speech",
        headers={"Authorization": "Bearer test-key"},
        json={"input": "Hello", "response_format": "mp3"},
    )
    assert response.status_code == 400


def test_tts_module_has_no_agora_dependency():
    import ast
    import inspect

    import tts

    tree = ast.parse(inspect.getsource(tts))
    imported_roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported_roots.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_roots.add(node.module.split(".")[0])

    agora_imports = sorted(root for root in imported_roots if root.startswith("agora"))
    assert not agora_imports, f"tts.py must not import an Agora SDK; found: {agora_imports}"
