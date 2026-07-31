"""Construction smoke: the real AgoraAgent is built and a session is created (SDK session faked).

Closes the gap where the rest of the suite stubs the whole Agent (FakeAgent) and never
exercises AgoraAgent construction — the exact path that agora-agents 2.3.x changed.
"""
import asyncio
import sys


def _fresh_agent_module():
    sys.modules.pop("agent", None)
    import agent
    return agent


def test_start_constructs_real_agent_and_returns_shape(fake_env, monkeypatch):
    agent = _fresh_agent_module()
    captured = {}

    class FakeSession:
        async def start(self):
            return "test-agent-id"

        async def stop(self):
            captured["stopped"] = True

    def fake_create_async_session(self, **kwargs):
        captured["channel"] = kwargs.get("channel")
        captured["remote_uids"] = kwargs.get("remote_uids")
        return FakeSession()

    from agora_agent.agentkit import Agent as AgoraAgent
    monkeypatch.setattr(AgoraAgent, "create_async_session", fake_create_async_session)

    instance = agent.Agent()
    result = asyncio.run(instance.start(channel_name="ch", agent_uid=111, user_uid=222))

    assert result["agent_id"] == "test-agent-id"
    assert result["channel_name"] == "ch"
    assert result["status"] == "started"
    assert captured["channel"] == "ch"
    assert captured["remote_uids"] == ["222"]


def test_generic_tts_serializes_for_http_extension(fake_env):
    agent = _fresh_agent_module()
    instance = agent.Agent()

    config = agent.GenericHttpTTS(
        url=instance.custom_tts_url,
        headers={},
        api_key=instance.custom_tts_api_key,
        model=instance.custom_tts_model,
        voice=instance.custom_tts_voice,
        speed=1,
        sample_rate=24000,
        response_format="pcm",
        instruction=(
            "Please use standard American English, natural tone, "
            "moderate pace, and steady intonation"
        ),
        additional_params={"app_id": instance.custom_tts_app_id},
    ).to_config()

    assert config == {
        "vendor": "generic_http",
        "url": "https://example.ngrok-free.dev/tts/v1/audio/speech",
        "params": {
            "api_key": "test-key",
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
    }
