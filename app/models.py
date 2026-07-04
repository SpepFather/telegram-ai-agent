"""
Pydantic-модели для API-эндпоинтов.
"""

from pydantic import BaseModel, Field


class EnvUpdate(BaseModel):
    """Тело запроса для обновления .env (секретные ключи)."""
    TELEGRAM_API_ID: int = Field(default=0, description="Telegram API ID")
    TELEGRAM_API_HASH: str = Field(default="", description="Telegram API Hash")
    OPENAI_API_KEY: str = Field(default="", description="OpenAI API Key")
    OPENAI_BASE_URL: str = Field(default="https://api.openmodel.ai/v1", description="Base URL API")
    AI_MODEL: str = Field(default="deepseek-v4-flash", description="Название модели")
    API_FORMAT: str = Field(default="openai", description="Формат API: openai или anthropic")


class ConfigUpdate(BaseModel):
    """Тело запроса для обновления config.json."""
    allowed_contacts: list[str] = Field(default_factory=list)
    system_prompt: str = Field(default="Ты — дружелюбный собеседник.")
    min_delay: float = Field(default=1.0, ge=0.0, le=10.0)
    max_delay: float = Field(default=3.0, ge=0.0, le=10.0)
    context_enabled: bool = Field(default=True)
    context_messages: int = Field(default=6, ge=1, le=50)


class StatusResponse(BaseModel):
    """Стандартный ответ о статусе."""
    status: str
    message: str
