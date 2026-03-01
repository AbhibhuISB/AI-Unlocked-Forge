from __future__ import annotations

import json
import os
from typing import Any, Type, TypeVar

from openai import AzureOpenAI, OpenAI
from pydantic import BaseModel


T = TypeVar("T", bound=BaseModel)


class LLMClient:
    def __init__(self) -> None:
        provider = os.getenv("LLM_PROVIDER", "azure").lower()
        self.provider = provider

        if provider == "azure":
            self.client = AzureOpenAI(
                api_key=os.getenv("AZURE_OPENAI_API_KEY", ""),
                azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT", ""),
                api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21"),
            )
            self.model = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
        else:
            self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY", ""))
            self.model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    def complete_text(self, system_prompt: str, user_prompt: str) -> str:
        response = self.client.responses.create(
            model=self.model,
            input=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
        )
        return response.output_text

    def complete_json(self, system_prompt: str, user_prompt: str, schema: Type[T]) -> T:
        raw = self.complete_text(system_prompt=system_prompt, user_prompt=user_prompt)
        try:
            parsed: Any = json.loads(raw)
            return schema.model_validate(parsed)
        except Exception:
            start = raw.find("{")
            end = raw.rfind("}")
            if start >= 0 and end > start:
                parsed = json.loads(raw[start : end + 1])
                return schema.model_validate(parsed)
            raise
