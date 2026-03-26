import logging
from dataclasses import dataclass
from typing import Optional

import google.generativeai as genai

logger = logging.getLogger(__name__)


@dataclass
class LLMResponse:
    text: str


class LLMClient:
    """Small wrapper to keep LLM usage consistent across modules."""

    def __init__(self, api_key: str, model: str = "gemini-1.5-flash"):
        self.api_key = api_key
        self.model_name = model
        self._model: Optional[genai.GenerativeModel] = None

        if api_key:
            genai.configure(api_key=api_key)
            self._model = genai.GenerativeModel(model_name=model)
        else:
            logger.warning("LLMClient initialized without API key")

    @property
    def is_enabled(self) -> bool:
        return self._model is not None

    def generate_content(self, prompt: str) -> LLMResponse:
        if not self._model:
            raise RuntimeError("LLM client is disabled because API key is missing")

        response = self._model.generate_content(prompt)
        text = getattr(response, "text", "") or ""
        return LLMResponse(text=text.strip())

    def ask(self, prompt: str) -> str:
        return self.generate_content(prompt).text
