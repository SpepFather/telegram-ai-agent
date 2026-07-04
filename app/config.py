"""
Модуль загрузки и сохранения конфигурации.
Читает/пишет .env и config.json через единое API.
"""

import json
import os
from pathlib import Path
from dotenv import load_dotenv, set_key, dotenv_values
from pydantic_settings import BaseSettings


# === Пути к файлам (от корня проекта) ===
BASE_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BASE_DIR / ".env"
CONFIG_FILE = BASE_DIR / "config.json"


# ============================
# config.json (runtime config)
# ============================

def load_config_json() -> dict:
    """Загружает config.json и возвращает словарь."""
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "allowed_contacts": [],
        "system_prompt": "Ты — дружелюбный собеседник.",
        "min_delay": 1.0,
        "max_delay": 3.0,
        "context_enabled": True,
        "context_messages": 6,
    }


def save_config_json(data: dict) -> None:
    """Сохраняет словарь в config.json с красивым форматированием."""
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ============================
# .env (секретные ключи)
# ============================

def _safe_int(value, default=0) -> int:
    """Безопасно преобразует значение в int."""
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def load_env_vars() -> dict:
    """
    Загружает все переменные из .env и возвращает словарь.
    Значения по умолчанию подставляются, если переменной нет.
    """
    vals = dotenv_values(str(ENV_FILE))  # не трогает os.environ
    return {
        "TELEGRAM_API_ID": _safe_int(vals.get("TELEGRAM_API_ID", "0"), 0),
        "TELEGRAM_API_HASH": vals.get("TELEGRAM_API_HASH", ""),
        "OPENAI_API_KEY": vals.get("OPENAI_API_KEY", ""),
        "OPENAI_BASE_URL": vals.get("OPENAI_BASE_URL", "https://api.openmodel.ai/v1"),
        "AI_MODEL": vals.get("AI_MODEL", "deepseek-v4-flash"),
        "API_FORMAT": vals.get("API_FORMAT", "openai"),
    }


def save_env_vars(data: dict) -> None:
    """
    Сохраняет выбранные ключи в .env (не удаляет остальные).
    Пропускает значения None/undefined — для сохранения маскированных полей.
    Обновляет глобальный settings singleton.
    """
    writable_keys = [
        "TELEGRAM_API_ID",
        "TELEGRAM_API_HASH",
        "OPENAI_API_KEY",
        "OPENAI_BASE_URL",
        "AI_MODEL",
        "API_FORMAT",
    ]
    for key in writable_keys:
        if key in data and data[key] is not None:
            set_key(str(ENV_FILE), key, str(data[key]), quote_mode="never")
    # Перечитываем в os.environ для текущего процесса
    load_dotenv(str(ENV_FILE), override=True)
    # Обновляем глобальный settings
    _reload_settings()


# ============================
# Pydantic Settings (runtime)
# ============================

class Settings(BaseSettings):
    """Настройки из переменных окружения (.env)."""

    TELEGRAM_API_ID: int = 0
    TELEGRAM_API_HASH: str = ""
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = "https://api.openmodel.ai/v1"
    AI_MODEL: str = "deepseek-v4-flash"
    API_FORMAT: str = "openai"

    model_config = {
        "env_file": str(ENV_FILE),
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


# Инициализация при импорте
load_dotenv(str(ENV_FILE), override=False)
_api_id_raw = os.getenv("TELEGRAM_API_ID", "0")
settings = Settings(TELEGRAM_API_ID=_safe_int(_api_id_raw, 0))


def _reload_settings() -> None:
    """Перечитывает .env и обновляет глобальный settings."""
    load_dotenv(str(ENV_FILE), override=True)
    global settings
    raw_id = os.getenv("TELEGRAM_API_ID", "0")
    new_settings = Settings(TELEGRAM_API_ID=_safe_int(raw_id, 0))
    # Обновляем поля объекта in-place, чтобы ссылки из других модулей остались рабочими
    for field, value in new_settings.model_dump().items():
        setattr(settings, field, value)
