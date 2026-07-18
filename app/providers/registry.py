from __future__ import annotations

from app.core.config import Settings
from app.domain.enums import AIProvider
from app.domain.models import Tenant
from app.prompts.loader import PromptLoader
from app.providers.base import VoiceProvider
from app.providers.gemini import GeminiProvider
from app.providers.openai import OpenAIRealtimeProvider
from app.tools.router import ToolRouter


class ProviderRegistry:
    def __init__(
        self,
        settings: Settings,
        tool_router: ToolRouter,
        prompt_loader: PromptLoader,
    ) -> None:
        self._settings = settings
        self._tool_router = tool_router
        self._prompt_loader = prompt_loader

    def create(self, tenant: Tenant) -> VoiceProvider:
        if tenant.ai_provider == AIProvider.OPENAI:
            return OpenAIRealtimeProvider()
        return GeminiProvider(
            settings=self._settings,
            tenant=tenant,
            tool_router=self._tool_router,
            prompt_loader=self._prompt_loader,
        )
