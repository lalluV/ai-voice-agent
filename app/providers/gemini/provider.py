from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

from app.core.config import Settings
from app.core.logging import get_logger
from app.core.metrics import ERRORS, RECONNECTS
from app.domain.models import CallSession, Tenant, ToolCall, ToolResult
from app.prompts.loader import PromptLoader
from app.providers.base import ProviderAudioEvent, ProviderEventType, VoiceProvider
from app.tools.definitions import gemini_function_declarations
from app.tools.router import ToolRouter

logger = get_logger(__name__)


class GeminiProvider(VoiceProvider):
    """
    Gemini 3.1 Flash Live provider using google-genai Live API.

    Audio: PCM16 16 kHz in / 24 kHz out.
    Interruption: server_content.interrupted → ProviderEventType.INTERRUPTED
    Tools: synchronous function calling (3.1 does not yet support async FC).
    """

    def __init__(
        self,
        *,
        settings: Settings,
        tenant: Tenant,
        tool_router: ToolRouter,
        prompt_loader: PromptLoader,
    ) -> None:
        self._settings = settings
        self._tenant = tenant
        self._tool_router = tool_router
        self._prompt_loader = prompt_loader
        self._session: CallSession | None = None
        self._live = None
        self._live_cm = None
        self._client = None
        self._queue: asyncio.Queue[ProviderAudioEvent | None] = asyncio.Queue()
        self._receive_task: asyncio.Task | None = None
        self._connected = False

    async def connect(self, session: CallSession) -> None:
        self._session = session
        api_key = self._tenant.gemini_api_key or self._settings.gemini_api_key
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY not configured")

        try:
            from google import genai
            from google.genai import types
        except ImportError as exc:
            raise RuntimeError("google-genai package is required") from exc

        system_instruction = self._prompt_loader.build_system_instruction(
            self._tenant.prompt_version,
            hospital_name=self._tenant.name,
            hospital_blurb=self._tenant.hospital_blurb,
        )

        self._client = genai.Client(api_key=api_key)
        model = self._settings.gemini_model
        voice_name = self._tenant.voice_name or self._settings.gemini_voice_name

        # Build Live config — fields may evolve; keep aligned with google-genai docs.
        tools = [{"function_declarations": gemini_function_declarations()}]
        config: dict[str, Any] = {
            "response_modalities": ["AUDIO"],
            "system_instruction": system_instruction,
            "tools": tools,
            "speech_config": {
                "voice_config": {
                    "prebuilt_voice_config": {"voice_name": voice_name}
                }
            },
        }
        # Prefer low thinking latency when supported by SDK/model
        try:
            config["thinking_config"] = {"thinking_level": "minimal"}
        except Exception:  # pragma: no cover
            pass

        self._live_cm = self._client.aio.live.connect(model=model, config=config)
        self._live = await self._live_cm.__aenter__()
        self._connected = True
        self._receive_task = asyncio.create_task(
            self._receive_loop(types), name=f"gemini-recv-{session.session_id}"
        )
        logger.info(
            "gemini_connected",
            model=model,
            session_id=session.session_id,
            tenant_id=self._tenant.tenant_id,
        )

    async def disconnect(self) -> None:
        self._connected = False
        if self._receive_task:
            self._receive_task.cancel()
            await asyncio.gather(self._receive_task, return_exceptions=True)
            self._receive_task = None
        await self._queue.put(None)
        if self._live is not None:
            try:
                await self._live_cm.__aexit__(None, None, None)
            except Exception:  # pragma: no cover
                logger.exception("gemini_disconnect_error")
            self._live = None
        logger.info(
            "gemini_disconnected",
            tenant_id=self._tenant.tenant_id,
            session_id=self._session.session_id if self._session else None,
        )

    async def send_audio(self, pcm16_16k: bytes) -> None:
        if not self._connected or self._live is None or not pcm16_16k:
            return
        from google.genai import types

        await self._live.send_realtime_input(
            audio=types.Blob(
                data=pcm16_16k,
                mime_type=f"audio/pcm;rate={self._settings.gemini_input_sample_rate}",
            )
        )

    async def audio_stream(self) -> AsyncIterator[ProviderAudioEvent]:
        while True:
            event = await self._queue.get()
            if event is None:
                break
            yield event

    async def handle_tool_call(self, call: ToolCall) -> ToolResult:
        assert self._session is not None
        return await self._tool_router.execute(
            tenant=self._tenant, session=self._session, call=call
        )

    async def send_tool_result(self, result: ToolResult) -> None:
        if self._live is None:
            return
        from google.genai import types

        response = types.FunctionResponse(
            id=result.id,
            name=result.name,
            response={
                "success": result.success,
                "data": result.data,
                "error": result.error,
            },
        )
        await self._live.send_tool_response(function_responses=[response])

    async def _receive_loop(self, types: Any) -> None:
        assert self._live is not None
        assert self._session is not None
        try:
            async for response in self._live.receive():
                await self._handle_response(response, types)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            ERRORS.labels(component="gemini").inc()
            RECONNECTS.labels(tenant_id=self._tenant.tenant_id).inc()
            logger.exception("gemini_receive_failed")
            await self._queue.put(
                ProviderAudioEvent(type=ProviderEventType.ERROR, error=str(exc))
            )
        finally:
            await self._queue.put(None)

    async def _handle_response(self, response: Any, types: Any) -> None:
        sc = getattr(response, "server_content", None)
        if sc is not None:
            if getattr(sc, "interrupted", False):
                if self._session:
                    self._session.interruption_count += 1
                await self._queue.put(
                    ProviderAudioEvent(type=ProviderEventType.INTERRUPTED)
                )
            # Audio parts
            model_turn = getattr(sc, "model_turn", None)
            if model_turn and getattr(model_turn, "parts", None):
                for part in model_turn.parts:
                    inline = getattr(part, "inline_data", None)
                    if inline and getattr(inline, "data", None):
                        await self._queue.put(
                            ProviderAudioEvent(
                                type=ProviderEventType.AUDIO,
                                pcm16=inline.data,
                                sample_rate=self._settings.gemini_output_sample_rate,
                            )
                        )
                    text = getattr(part, "text", None)
                    if text:
                        await self._queue.put(
                            ProviderAudioEvent(type=ProviderEventType.TEXT, text=text)
                        )
            if getattr(sc, "turn_complete", False):
                await self._queue.put(
                    ProviderAudioEvent(type=ProviderEventType.TURN_COMPLETE)
                )

        tool_call = getattr(response, "tool_call", None)
        if tool_call and getattr(tool_call, "function_calls", None):
            for fc in tool_call.function_calls:
                args = fc.args if isinstance(fc.args, dict) else {}
                if isinstance(fc.args, str):
                    try:
                        args = json.loads(fc.args)
                    except json.JSONDecodeError:
                        args = {"raw": fc.args}
                call = ToolCall(
                    id=getattr(fc, "id", None) or fc.name,
                    name=fc.name,
                    arguments=args or {},
                )
                await self._queue.put(
                    ProviderAudioEvent(
                        type=ProviderEventType.TOOL_CALL, tool_call=call
                    )
                )
                result = await self.handle_tool_call(call)
                await self.send_tool_result(result)
