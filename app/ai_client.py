"""
AI-клиент: поддержка OpenAI и Anthropic Messages API.
Выбирает формат в зависимости от API_FORMAT (.env).
"""

import json
import logging
from openai import AsyncOpenAI
import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class AIClient:
    """
    Асинхронный клиент для AI API.
    Поддерживает форматы:
      - 'openai'   → POST /v1/chat/completions (OpenAI SDK)
      - 'anthropic' → POST /v1/messages (Anthropic Messages API)
    """

    def __init__(self):
        self.api_key = settings.OPENAI_API_KEY
        self.base_url = settings.OPENAI_BASE_URL.rstrip("/")
        self.model = settings.AI_MODEL
        self.api_format = (settings.API_FORMAT or "openai").lower()

        # OpenAI client (используется только при format='openai')
        self._openai = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
        )

    async def generate_response(
        self,
        message: str,
        system_prompt: str,
        messages: list[dict] | None = None,
    ) -> str:
        """
        Генерирует ответ.
        Если передан messages (с историей) — использует его.
        Если нет — собирает простой запрос (system + user).
        """
        if messages is not None:
            # Используем переданную историю (уже включает system_prompt и все сообщения)
            pass
        else:
            # Собираем простой запрос
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": message},
            ]

        if self.api_format == "anthropic":
            return await self._generate_anthropic(message, system_prompt, messages)
        else:
            return await self._generate_openai(message, system_prompt, messages)

    # ========== OpenAI-формат ==========

    async def _generate_openai(
        self, message: str, system_prompt: str,
        messages: list[dict] | None = None,
    ) -> str:
        logger.info(f"[OpenAI] {self.model}: {len(messages or [])} сообщений")
        try:
            response = await self._openai.chat.completions.create(
                model=self.model,
                messages=messages or [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": message},
                ],
                max_tokens=1024,
                temperature=0.7,
            )
            answer = response.choices[0].message.content.strip()
            logger.info(f"[OpenAI] Ответ: {answer[:80]}...")
            return answer
        except Exception as e:
            logger.error(f"[OpenAI] Ошибка: {e}")
            raise

    # ========== Anthropic-формат (/v1/messages) ==========

    async def _generate_anthropic(
        self, message: str, system_prompt: str,
        messages: list[dict] | None = None,
    ) -> str:
        logger.info(f"[Anthropic] {self.model}: {len(messages or [])} сообщений")

        # Для Anthropic-формата путь всегда /v1/messages
        base = self.base_url.rstrip("/")
        if not base.endswith("/v1"):
            base += "/v1"
        url = f"{base}/messages"
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
        }
        # Для Anthropic: system prompt отдельно, messages только user/assistant
        anthropic_msgs = []
        anthropic_sys = system_prompt
        if messages:
            for m in messages:
                role = m.get("role", "")
                if role == "system":
                    anthropic_sys = m.get("content", "")
                elif role in ("user", "assistant"):
                    anthropic_msgs.append({
                        "role": "user" if role == "user" else "assistant",
                        "content": m.get("content", ""),
                    })
        if not anthropic_msgs:
            anthropic_msgs = [{"role": "user", "content": message}]

        payload = {
            "model": self.model,
            "max_tokens": 1024,
            "messages": anthropic_msgs,
        }
        if anthropic_sys:
            payload["system"] = anthropic_sys

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(url, headers=headers, json=payload)
                resp.raise_for_status()
                data = resp.json()

            # Парсим Anthropic-ответ
            answer = self._parse_anthropic_response(data)
            logger.info(f"[Anthropic] Ответ: {answer[:80]}...")
            return answer

        except httpx.HTTPStatusError as e:
            detail = ""
            try:
                detail = f": {e.response.text[:200]}"
            except Exception:
                pass
            error_msg = f"HTTP {e.response.status_code}{detail}"
            logger.error(f"[Anthropic] Ошибка: {error_msg}")
            raise Exception(error_msg)

        except Exception as e:
            logger.error(f"[Anthropic] Ошибка: {e}")
            raise

    @staticmethod
    def _parse_anthropic_response(data: dict) -> str:
        """Извлекает текст из ответа Anthropic Messages API."""
        content = data.get("content", [])
        texts = []
        for block in content:
            if block.get("type") == "text":
                texts.append(block.get("text", ""))
        if not texts:
            # fallback: берём всё content как строку
            return str(content)
        return "\n".join(texts).strip()


# Глобальный экземпляр
ai_client = AIClient()
