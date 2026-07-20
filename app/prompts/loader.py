from __future__ import annotations

import time
from pathlib import Path

from app.core.logging import get_logger

logger = get_logger(__name__)

PROMPTS_ROOT = Path(__file__).resolve().parent / "versions"


class PromptLoader:
    """Load versioned prompt files with mtime-based reload."""

    def __init__(self, root: Path | None = None) -> None:
        self._root = root or PROMPTS_ROOT
        self._cache: dict[str, tuple[float, str]] = {}

    def _path(self, version: str, name: str) -> Path:
        return self._root / version / name

    def load(self, version: str, name: str) -> str:
        path = self._path(version, name)
        key = str(path)
        mtime = path.stat().st_mtime if path.exists() else 0.0
        cached = self._cache.get(key)
        if cached and cached[0] == mtime:
            return cached[1]
        text = path.read_text(encoding="utf-8")
        self._cache[key] = (mtime, text)
        logger.debug("prompt_loaded", version=version, name=name, mtime=mtime)
        return text

    def build_system_instruction(
        self,
        version: str,
        *,
        hospital_name: str,
        hospital_blurb: str | None = None,
        caller_number: str | None = None,
        caller_number_spoken: str | None = None,
    ) -> str:
        receptionist = self.load(version, "system_receptionist.md")
        language = self.load(version, "language_policy.md")
        tools = self.load(version, "tool_use.md")
        blurb = hospital_blurb or f"You represent {hospital_name}."
        header = (
            f"# Hospital context\n"
            f"Hospital name: {hospital_name}\n"
            f"{blurb}\n"
            f"Prompt version: {version}\n"
            f"Loaded at: {int(time.time())}\n"
        )
        if caller_number:
            spoken = caller_number_spoken or caller_number
            header += (
                f"\n# Caller on this line\n"
                f"Calling number (known from the phone network): {caller_number}\n"
                f"Say it naturally as: {spoken}\n"
                f"Whenever any flow needs a phone number, offer this number first "
                f"(use this or another?), then read back the chosen number to verify.\n"
            )
        else:
            header += (
                "\n# Caller on this line\n"
                "Calling number is unknown. If a phone is needed, ask for it, "
                "then read it back once to verify before using it.\n"
            )
        header += "\n"
        return "\n\n".join([header, receptionist, language, tools])


prompt_loader = PromptLoader()
