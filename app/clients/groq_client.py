from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from app.core.config import BASE_DIR, Settings
from app.core.exceptions import ExternalServiceError, NotConfiguredError


class GroqClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.prompt_dir = BASE_DIR / "app" / "prompts"

    def generate_text(self, prompt_name: str, user_prompt: str, *, temperature: float = 0.1) -> str:
        llm = self._build_llm(temperature=temperature)
        system_prompt = self._load_prompt(prompt_name)
        try:
            from langchain_core.messages import HumanMessage, SystemMessage
        except ImportError as exc:
            raise NotConfiguredError("langchain-core is required to send Groq prompts.") from exc

        response = llm.invoke(
            [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt),
            ]
        )
        content = response.content
        if isinstance(content, list):
            return "\n".join(str(item) for item in content)
        return str(content).strip()

    def generate_json(self, prompt_name: str, user_prompt: str, *, temperature: float = 0.0) -> Any:
        raw = self.generate_text(prompt_name, user_prompt, temperature=temperature)
        return self._extract_json(raw)

    def _build_llm(self, *, temperature: float):
        if not self.settings.groq_api_key or not self.settings.groq_model:
            raise NotConfiguredError(
                "GROQ_API_KEY and GROQ_MODEL must be configured before generation features can be used."
            )
        try:
            from langchain_groq import ChatGroq
        except ImportError as exc:
            raise NotConfiguredError("langchain-groq is required for Groq generation.") from exc

        return ChatGroq(
            api_key=self.settings.groq_api_key.get_secret_value(),
            model_name=self.settings.groq_model,
            temperature=temperature,
        )

    def _load_prompt(self, prompt_name: str) -> str:
        prompt_path = self.prompt_dir / prompt_name
        return prompt_path.read_text(encoding="utf-8").strip()

    @staticmethod
    def _extract_json(raw: str) -> Any:
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            fenced = re.search(r"```json\s*(.*?)\s*```", raw, flags=re.IGNORECASE | re.DOTALL)
            if fenced:
                try:
                    return json.loads(fenced.group(1))
                except json.JSONDecodeError as exc:
                    raise ExternalServiceError("The language model returned invalid JSON.") from exc
        raise ExternalServiceError("The language model did not return JSON in the expected format.")
