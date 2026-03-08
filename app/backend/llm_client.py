from __future__ import annotations

import json
import os
import re
from typing import Any

import httpx

from app.backend.config import load_local_env


load_local_env()


class LLMClient:
    def __init__(self) -> None:
        self.api_key = os.getenv('OPENAI_API_KEY', '')
        self.base_url = os.getenv('OPENAI_BASE_URL', '').rstrip('/')
        self.model = os.getenv('OPENAI_MODEL', '')
        self.enabled = bool(self.api_key and self.base_url and self.model)
        self.blocked_reason = ''

    def chat_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.1,
        max_tokens: int = 1800,
    ) -> dict[str, Any]:
        content = self.chat_text(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return self._extract_json(content)

    def chat_text(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
        max_tokens: int = 1200,
    ) -> str:
        if not self.enabled:
            raise RuntimeError('LLM client is not configured.')

        payload = {
            'model': self.model,
            'messages': [
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_prompt},
            ],
            'temperature': temperature,
            'max_tokens': max_tokens,
        }
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
        }
        with httpx.Client(timeout=60.0) as client:
            response = client.post(f'{self.base_url}/chat/completions', headers=headers, json=payload)
            if response.status_code >= 400:
                if response.status_code == 403 and 'not enough quota' in response.text:
                    self.enabled = False
                    self.blocked_reason = 'model_quota_exhausted'
                response.raise_for_status()
            data = response.json()
        return data['choices'][0]['message']['content']

    @staticmethod
    def _extract_json(content: str) -> dict[str, Any]:
        if isinstance(content, dict):
            return content
        text = content.strip()
        fenced = re.search(r'```(?:json)?\s*(\{.*\}|\[.*\])\s*```', text, re.S)
        if fenced:
            text = fenced.group(1)
        if text.startswith('{') or text.startswith('['):
            return json.loads(text)
        start = text.find('{')
        end = text.rfind('}')
        if start != -1 and end != -1 and end > start:
            return json.loads(text[start : end + 1])
        raise ValueError(f'No JSON object found in LLM output: {content[:200]}')
