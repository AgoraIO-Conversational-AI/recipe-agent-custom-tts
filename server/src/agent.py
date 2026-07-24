"""Agora Conversational AI agent configured with a custom HTTP TTS endpoint."""

import logging
import os
from typing import Any, Dict, Optional

from agora_agent import Area, AsyncAgora
from agora_agent.agentkit import Agent as AgoraAgent
from agora_agent.agentkit.vendors import DeepgramSTT, GenericTTS, OpenAI

logger = logging.getLogger("uvicorn.error")


class GenericHttpTTS(GenericTTS):
    """Use the current cloud vendor name with the published SDK."""

    def to_config(self) -> Dict[str, Any]:
        config = super().to_config()
        config["vendor"] = "generic_http"
        if not config.get("headers"):
            config.pop("headers", None)
        return config


class Agent:
    """Manage an Agora agent whose TTS stage calls a public HTTP endpoint."""

    def __init__(self):
        self.app_id = os.getenv("AGORA_APP_ID")
        self.app_certificate = os.getenv("AGORA_APP_CERTIFICATE")
        self.greeting = os.getenv(
            "AGENT_GREETING",
            "Hi! This response is synthesized by a custom HTTP TTS endpoint.",
        )
        self.custom_tts_url = os.getenv("CUSTOM_TTS_URL")
        self.custom_tts_api_key = os.getenv("CUSTOM_TTS_API_KEY", "any-key-here")
        self.custom_tts_app_id = os.getenv("CUSTOM_TTS_APP_ID")
        self.custom_tts_model = os.getenv("CUSTOM_TTS_MODEL", "mock-tts")
        self.custom_tts_voice = os.getenv("CUSTOM_TTS_VOICE", "mock-voice")

        if not self.app_id or not self.app_certificate:
            raise ValueError("AGORA_APP_ID and AGORA_APP_CERTIFICATE are required")
        if not self.custom_tts_url:
            raise ValueError(
                "CUSTOM_TTS_URL is required (for local development, use the public "
                "URL ending in /tts/v1/audio/speech)"
            )
        if not self.custom_tts_api_key:
            raise ValueError("CUSTOM_TTS_API_KEY must not be empty")
        if not self.custom_tts_app_id:
            raise ValueError("CUSTOM_TTS_APP_ID is required")

        self.client = AsyncAgora(
            area=Area.US,
            app_id=self.app_id,
            app_certificate=self.app_certificate,
        )
        self._sessions: Dict[str, Any] = {}

    async def start(
        self,
        channel_name: str,
        agent_uid: int,
        user_uid: int,
        output_audio_codec: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Start an agent using the configured GenericTTS endpoint."""
        if not channel_name or not str(channel_name).strip():
            raise ValueError("channel_name is required and cannot be empty")
        if agent_uid <= 0:
            raise ValueError("agent_uid is required and cannot be empty")
        if user_uid <= 0:
            raise ValueError("user_uid is required and cannot be empty")

        stt = DeepgramSTT(model="nova-3", language="en")
        llm = OpenAI(model="gpt-4o-mini")
        tts = GenericHttpTTS(
            url=self.custom_tts_url,
            headers={},
            api_key=self.custom_tts_api_key,
            model=self.custom_tts_model,
            voice=self.custom_tts_voice,
            speed=1,
            sample_rate=24000,
            response_format="pcm",
            instruction=(
                "Please use standard American English, natural tone, "
                "moderate pace, and steady intonation"
            ),
            additional_params={"app_id": self.custom_tts_app_id},
        )

        parameters = {
            "audio_scenario": "chorus",
            "data_channel": "rtm",
            "enable_error_message": True,
            "enable_metrics": True,
        }
        if isinstance(output_audio_codec, str) and output_audio_codec.strip():
            parameters["output_audio_codec"] = output_audio_codec.strip()

        agora_agent = AgoraAgent(
            client=self.client,
            instructions="Keep responses brief and conversational.",
            greeting=self.greeting,
            failure_message="Please wait a moment.",
            max_history=50,
            turn_detection={
                "config": {
                    "speech_threshold": 0.5,
                    "start_of_speech": {
                        "mode": "vad",
                        "vad_config": {
                            "interrupt_duration_ms": 160,
                            "prefix_padding_ms": 300,
                        },
                    },
                    "end_of_speech": {
                        "mode": "vad",
                        "vad_config": {
                            "silence_duration_ms": 480,
                        },
                    },
                },
            },
            advanced_features={"enable_rtm": True},
            parameters=parameters,
        )
        agora_agent = agora_agent.with_stt(stt).with_llm(llm).with_tts(tts)

        session = agora_agent.create_async_session(
            channel=channel_name,
            agent_uid=str(agent_uid),
            remote_uids=[str(user_uid)],
            enable_string_uid=False,
            idle_timeout=30,
            expires_in=3600,
        )

        logger.info(
            "Starting custom TTS agent channel=%s agent_uid=%s user_uid=%s tts_url=%s",
            channel_name,
            agent_uid,
            user_uid,
            self.custom_tts_url,
        )
        try:
            agent_id = await session.start()
        except Exception:
            logger.exception(
                "Failed to start custom TTS agent channel=%s agent_uid=%s user_uid=%s",
                channel_name,
                agent_uid,
                user_uid,
            )
            raise

        self._sessions[agent_id] = session
        logger.info("Started custom TTS agent agent_id=%s channel=%s", agent_id, channel_name)
        return {
            "agent_id": agent_id,
            "channel_name": channel_name,
            "status": "started",
        }

    async def stop(self, agent_id: str) -> None:
        """Stop a running agent. Falls back to the stateless client path."""
        if not agent_id or not str(agent_id).strip():
            raise ValueError("agent_id is required and cannot be empty")

        session = self._sessions.pop(agent_id, None)
        if session:
            try:
                await session.stop()
                logger.info("Stopped agent from active session agent_id=%s", agent_id)
                return
            except Exception:
                logger.warning(
                    "Failed to stop agent from active session; falling back agent_id=%s",
                    agent_id,
                    exc_info=True,
                )

        logger.info("Stopping agent through client.stop_agent agent_id=%s", agent_id)
        await self.client.stop_agent(agent_id)
