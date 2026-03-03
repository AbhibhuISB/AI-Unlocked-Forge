from __future__ import annotations

import json
import os
from urllib.parse import urlparse
from typing import Any, Type, TypeVar

import httpx
from openai import AzureOpenAI, OpenAI
from pydantic import BaseModel


T = TypeVar("T", bound=BaseModel)


class LLMClient:
    def __init__(self) -> None:
        provider = (os.getenv("LLM_PROVIDER", "azure") or "azure").strip().lower()
        self.provider = provider
        self.azure_mode = ""

        if provider == "azure":
            api_key = (os.getenv("AZURE_OPENAI_API_KEY", "") or "").strip()
            azure_endpoint = (os.getenv("AZURE_OPENAI_ENDPOINT", "") or "").strip()
            api_version = (os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21") or "2024-10-21").strip()
            host = (urlparse(azure_endpoint).netloc or "").lower()

            self.api_key = api_key
            self.azure_endpoint = azure_endpoint.rstrip("/")
            self.api_version = api_version
            self.model = (os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o") or "gpt-4o").strip()

            if host.endswith("openai.azure.com"):
                self.azure_mode = "azure_openai_resource"
                self.client = AzureOpenAI(
                    api_key=api_key,
                    azure_endpoint=azure_endpoint,
                    api_version=api_version,
                )
            elif host.endswith("services.ai.azure.com"):
                self.azure_mode = "azure_ai_foundry_project"
                self.client = None
            else:
                raise ValueError(
                    "Unsupported AZURE_OPENAI_ENDPOINT host. Use either "
                    "https://<resource>.openai.azure.com/ or "
                    "https://<resource>.services.ai.azure.com/api/projects/<project>."
                )
        else:
            self.client = OpenAI(api_key=(os.getenv("OPENAI_API_KEY", "") or "").strip())
            self.model = (os.getenv("OPENAI_MODEL", "gpt-4o-mini") or "gpt-4o-mini").strip()

    def complete_text(self, system_prompt: str, user_prompt: str) -> str:
        if self.provider != "azure":
            response = self.client.responses.create(
                model=self.model,
                input=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.2,
            )
            return response.output_text

        if self.azure_mode == "azure_openai_resource":
            try:
                response = self.client.responses.create(
                    model=self.model,
                    input=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=0.2,
                )
                return response.output_text
            except Exception as error:
                if "404" not in str(error):
                    raise

                completion = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=0.2,
                )
                choices = completion.choices or []
                if not choices:
                    raise RuntimeError("chat.completions returned no choices.")
                content = choices[0].message.content or ""
                return str(content)

        return self._complete_text_foundry(system_prompt=system_prompt, user_prompt=user_prompt)

    def _complete_text_foundry(self, system_prompt: str, user_prompt: str) -> str:
        url = f"{self.azure_endpoint}/models/chat/completions"
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
        }

        version_candidates = [
            self.api_version,
            "2024-05-01-preview",
            "2024-06-01",
            "2024-10-21",
        ]

        seen = set()
        ordered_versions = []
        for value in version_candidates:
            if value and value not in seen:
                ordered_versions.append(value)
                seen.add(value)

        last_error = None
        for version in ordered_versions:
            try:
                with httpx.Client(timeout=40) as client:
                    response = client.post(
                        url,
                        params={"api-version": version},
                        headers={
                            "api-key": self.api_key,
                            "Content-Type": "application/json",
                        },
                        json=payload,
                    )

                if response.status_code >= 400:
                    last_error = RuntimeError(
                        f"Foundry call failed (api-version={version}): {response.status_code} {response.text[:300]}"
                    )
                    continue

                data = response.json()
                choices = data.get("choices", [])
                if not choices:
                    raise RuntimeError("Foundry response had no choices.")

                message = choices[0].get("message", {})
                content = message.get("content", "")
                if isinstance(content, list):
                    text_parts = []
                    for item in content:
                        if isinstance(item, dict) and item.get("type") == "text":
                            text_parts.append(item.get("text", ""))
                    content = "\n".join([part for part in text_parts if part])

                return str(content)
            except Exception as error:
                last_error = error

        raise RuntimeError(f"Foundry endpoint call failed for all API versions. Last error: {last_error}")

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
