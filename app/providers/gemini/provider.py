from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator
from typing import Any

from app.core.config import Settings
from app.core.logging import get_logger
from app.core.metrics import ERRORS, RECONNECTS
from app.domain.enums import CallDirection
from app.domain.models import CallSession, Tenant, ToolCall, ToolResult
from app.prompts.loader import PromptLoader
from app.providers.base import ProviderAudioEvent, ProviderEventType, VoiceProvider
from app.tools.definitions import gemini_function_declarations
from app.tools.router import ToolRouter

logger = get_logger(__name__)


class GeminiProvider(VoiceProvider):
    """
    Gemini 3.1 Flash Live provider.

    - PCM16 16 kHz in / 24 kHz out
    - receive() is per-turn; outer loop keeps the session alive
    - Ignores self-interrupt noise during call-start grace window
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
        self._send_lock = asyncio.Lock()
        self._connected_at = 0.0
        self._ignore_interrupt_until = 0.0
        self._agent_speaking = False
        # Gemini Live rejects sendRealtimeInput while a tool call is pending
        # and closes the socket with 1008 (policy violation). Gate mic audio.
        self._tool_call_pending = False

    async def connect(self, session: CallSession) -> None:
        self._session = session
        api_key = self._tenant.gemini_api_key or self._settings.gemini_api_key
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY not configured")

        try:
            from google import genai
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

        tools = [{"function_declarations": gemini_function_declarations()}]
        # Tuned VAD: longer silence so brief pauses are not cut off;
        # slightly less eager start to reduce echo false barge-ins on PSTN.
        config: dict[str, Any] = {
            "response_modalities": ["AUDIO"],
            "system_instruction": system_instruction,
            "tools": tools,
            "speech_config": {
                "voice_config": {
                    "prebuilt_voice_config": {"voice_name": voice_name}
                }
            },
            "thinking_config": {"thinking_level": "minimal"},
            "realtime_input_config": {
                "automatic_activity_detection": {
                    "disabled": False,
                    "prefix_padding_ms": 200,
                    "silence_duration_ms": self._settings.gemini_vad_silence_ms,
                }
            },
        }

        self._live_cm = self._client.aio.live.connect(model=model, config=config)
        self._live = await self._live_cm.__aenter__()
        self._connected = True
        self._connected_at = time.monotonic()
        # Protect greeting from line/echo self-interrupt
        self._ignore_interrupt_until = (
            self._connected_at + self._settings.interrupt_grace_seconds
        )
        self._receive_task = asyncio.create_task(
            self._receive_loop(), name=f"gemini-recv-{session.session_id}"
        )

        try:
            await self._live.send_realtime_input(text=self._greeting_seed(session))
        except Exception:  # pragma: no cover
            logger.exception("gemini_greeting_seed_failed")

        logger.info(
            "gemini_connected",
            model=model,
            voice=voice_name,
            session_id=session.session_id,
            tenant_id=self._tenant.tenant_id,
            direction=session.direction,
        )

    def arm_greeting_grace(self) -> None:
        self._ignore_interrupt_until = (
            time.monotonic() + self._settings.interrupt_grace_seconds
        )

    def _greeting_seed(self, session: CallSession) -> str:
        name = self._tenant.name
        if session.direction == CallDirection.OUTBOUND:
            return (
                f"Outbound call — the person just answered. Hospital: {name}. "
                "Speak like a real hospital receptionist in everyday Telugu, "
                "one short natural sentence: say you are calling from the hospital, "
                "then ask if they need any help. "
                f"Example: 'నమస్కారం, {name} నుంచి మాట్లాడుతున్నాను. ఏమైనా సహాయం కావాలా?' "
                "Do not sound textbook or stiff. If they prefer English, switch. "
                "Do not call any tools yet."
            )
        return (
            f"Call connected. Hospital name: {name}. "
            "Speak like a real hospital receptionist in everyday Telugu, "
            "one short natural sentence: greet and ask how you can help. "
            f"Example: 'నమస్కారం, {name}. ఎలా సహాయం చేయాలి?' "
            "Do not sound textbook or stiff. If they prefer English, switch. "
            "Do not call any tools yet."
        )

    async def disconnect(self) -> None:
        self._connected = False
        if self._receive_task:
            self._receive_task.cancel()
            await asyncio.gather(self._receive_task, return_exceptions=True)
            self._receive_task = None
        await self._queue.put(None)
        if self._live is not None and self._live_cm is not None:
            try:
                await self._live_cm.__aexit__(None, None, None)
            except Exception:  # pragma: no cover
                logger.exception("gemini_disconnect_error")
            self._live = None
            self._live_cm = None
        logger.info(
            "gemini_disconnected",
            tenant_id=self._tenant.tenant_id,
            session_id=self._session.session_id if self._session else None,
        )

    def note_agent_speaking(self, speaking: bool) -> None:
        self._agent_speaking = speaking
        if speaking:
            # Brief shield against echo-triggered interrupt at start of each utterance
            self._ignore_interrupt_until = max(
                self._ignore_interrupt_until,
                time.monotonic() + self._settings.utterance_interrupt_grace_seconds,
            )

    async def send_audio(self, pcm16_16k: bytes) -> None:
        if not self._connected or self._live is None or not pcm16_16k:
            return
        # Soft half-duplex: while agent audio is playing, do not feed mic to Gemini.
        # Real barge-in still works after grace via Plivo clear + user speech after.
        if self._agent_speaking and time.monotonic() < self._ignore_interrupt_until:
            return
        if self._tool_call_pending:
            return
        from google.genai import types

        try:
            async with self._send_lock:
                # Re-check under lock: tool handler may have set the gate
                # between the early return above and acquiring the lock.
                if (
                    not self._connected
                    or self._live is None
                    or self._tool_call_pending
                ):
                    return
                await self._live.send_realtime_input(
                    audio=types.Blob(
                        data=pcm16_16k,
                        mime_type=(
                            f"audio/pcm;rate={self._settings.gemini_input_sample_rate}"
                        ),
                    )
                )
        except Exception:
            ERRORS.labels(component="gemini").inc()
            logger.exception(
                "gemini_send_audio_failed",
                session_id=self._session.session_id if self._session else None,
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

        payload: dict[str, Any] = {
            "success": result.success,
            "data": result.data,
            "error": result.error,
            "instruction": (
                "Speak this result to the caller now. "
                "Do not invent data. Do not call the same tool again unless "
                "the caller gave new information."
            ),
        }
        if isinstance(result.data, dict) and result.data.get("do_not_retry"):
            payload["do_not_retry"] = True
        response = types.FunctionResponse(
            id=result.id,
            name=result.name,
            response=payload,
        )
        async with self._send_lock:
            await self._live.send_tool_response(function_responses=[response])

    async def _receive_loop(self) -> None:
        assert self._live is not None
        try:
            while self._connected:
                turn = self._live.receive()
                async for response in turn:
                    if not self._connected:
                        break
                    await self._handle_response(response)
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

    def _should_honor_interrupt(self) -> bool:
        return time.monotonic() >= self._ignore_interrupt_until

    async def _handle_response(self, response: Any) -> None:
        data = getattr(response, "data", None)
        if data:
            self.note_agent_speaking(True)
            await self._queue.put(
                ProviderAudioEvent(
                    type=ProviderEventType.AUDIO,
                    pcm16=data,
                    sample_rate=self._settings.gemini_output_sample_rate,
                )
            )

        text = getattr(response, "text", None)
        if text:
            await self._queue.put(
                ProviderAudioEvent(type=ProviderEventType.TEXT, text=text)
            )

        sc = getattr(response, "server_content", None)
        if sc is not None:
            if getattr(sc, "interrupted", False):
                if self._should_honor_interrupt():
                    if self._session:
                        self._session.interruption_count += 1
                    self._agent_speaking = False
                    await self._queue.put(
                        ProviderAudioEvent(type=ProviderEventType.INTERRUPTED)
                    )
                    logger.info(
                        "gemini_interrupted",
                        session_id=self._session.session_id if self._session else None,
                    )
                else:
                    logger.info(
                        "gemini_interrupt_ignored_grace",
                        session_id=self._session.session_id if self._session else None,
                    )

            model_turn = getattr(sc, "model_turn", None)
            if model_turn and getattr(model_turn, "parts", None):
                for part in model_turn.parts:
                    inline = getattr(part, "inline_data", None)
                    if inline and getattr(inline, "data", None):
                        if data and inline.data is data:
                            continue
                        self.note_agent_speaking(True)
                        await self._queue.put(
                            ProviderAudioEvent(
                                type=ProviderEventType.AUDIO,
                                pcm16=inline.data,
                                sample_rate=self._settings.gemini_output_sample_rate,
                            )
                        )
                    part_text = getattr(part, "text", None)
                    if part_text and part_text != text:
                        await self._queue.put(
                            ProviderAudioEvent(
                                type=ProviderEventType.TEXT, text=part_text
                            )
                        )

            if getattr(sc, "turn_complete", False):
                self._agent_speaking = False
                await self._queue.put(
                    ProviderAudioEvent(type=ProviderEventType.TURN_COMPLETE)
                )
                logger.info(
                    "gemini_turn_complete",
                    session_id=self._session.session_id if self._session else None,
                )

        tool_call = getattr(response, "tool_call", None)
        if tool_call and getattr(tool_call, "function_calls", None):
            # Block mic audio until every functionResponse is sent; otherwise
            # Live aborts the session with websocket 1008. Set the gate under
            # the send lock so in-flight send_audio cannot race past it.
            async with self._send_lock:
                self._tool_call_pending = True
            try:
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
                    logger.info(
                        "gemini_tool_call",
                        tool=call.name,
                        session_id=(
                            self._session.session_id if self._session else None
                        ),
                    )
                    await self._queue.put(
                        ProviderAudioEvent(
                            type=ProviderEventType.TOOL_CALL, tool_call=call
                        )
                    )
                    # Do not send realtime text while a function call is pending —
                    # that confuses Live into more tool loops / silence.
                    result = await self.handle_tool_call(call)
                    await self.send_tool_result(result)
            finally:
                self._tool_call_pending = False
