"""
Главный модуль: FastAPI, WebSocket, REST-эндпоинты.
"""

import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from pydantic import BaseModel

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse

from app.config import (
    settings, load_config_json, save_config_json,
    load_env_vars, save_env_vars, BASE_DIR,
)
from app.models import ConfigUpdate, EnvUpdate, StatusResponse
from app import telegram_client

# === Логирование ===
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# === WebSocket-клиенты ===
connected_ws: list[WebSocket] = []


async def broadcast_log(entry: dict) -> None:
    """Рассылает лог всем подключённым WebSocket-клиентам."""
    if not connected_ws:
        return
    dead = []
    for ws in connected_ws:
        try:
            await ws.send_json(entry)
        except Exception:
            dead.append(ws)
    for ws in dead:
        connected_ws.remove(ws)


# === Lifespan ===
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    logger.info("Приложение запускается...")
    telegram_client.set_ws_log_callback(broadcast_log)
    yield
    logger.info("Приложение останавливается...")
    await telegram_client.stop_telegram_client()


# === FastAPI ===
app = FastAPI(
    title="Telegram AI Agent",
    version="2.0.0",
    lifespan=lifespan,
)

STATIC_DIR = BASE_DIR / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ============================================================
# Главная страница
# ============================================================
@app.get("/", response_class=HTMLResponse)
async def root():
    with open(STATIC_DIR / "index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())


# ============================================================
# Настройки — config.json (контакты, промпт)
# ============================================================
@app.get("/settings")
async def get_settings() -> dict:
    config = load_config_json()
    return {
        "allowed_contacts": config.get("allowed_contacts", []),
        "system_prompt": config.get("system_prompt", ""),
        "min_delay": config.get("min_delay", 1.0),
        "max_delay": config.get("max_delay", 3.0),
        "context_enabled": config.get("context_enabled", True),
        "context_messages": config.get("context_messages", 6),
    }


@app.post("/settings")
async def update_settings(data: ConfigUpdate) -> dict:
    new_config = {
        "allowed_contacts": data.allowed_contacts,
        "system_prompt": data.system_prompt,
        "min_delay": data.min_delay,
        "max_delay": data.max_delay,
        "context_enabled": data.context_enabled,
        "context_messages": data.context_messages,
    }
    save_config_json(new_config)
    await broadcast_log({
        "type": "info", "text": "Настройки (config.json) обновлены.",
        "sender": "system", "timestamp": "",
    })
    return {"status": "ok", "config": new_config}


# ============================================================
# Переменные окружения — .env (ключи API)
# ============================================================
@app.get("/env")
async def get_env() -> dict:
    """Возвращает env-переменные (ключи замаскированы)."""
    vals = load_env_vars()
    # Маскируем секреты для отображения
    key = vals.get("OPENAI_API_KEY", "")
    hash_val = vals.get("TELEGRAM_API_HASH", "")
    return {
        "TELEGRAM_API_ID": vals.get("TELEGRAM_API_ID", 0),
        "TELEGRAM_API_HASH": _mask(hash_val) if hash_val else "",
        "OPENAI_API_KEY": _mask(key) if key else "",
        "OPENAI_BASE_URL": vals.get("OPENAI_BASE_URL", ""),
        "AI_MODEL": vals.get("AI_MODEL", ""),
        "API_FORMAT": vals.get("API_FORMAT", "openai"),
        "has_telegram_keys": bool(vals.get("TELEGRAM_API_ID", 0) and hash_val),
        "has_openai_key": bool(key),
    }


def _mask(s: str, visible: int = 4) -> str:
    """Маскирует строку: sk-abc...xyz → sk-abc...yz"""
    if len(s) <= visible + 3:
        return s[:2] + "***"
    return s[:visible] + "***" + s[-2:]


@app.post("/env")
async def update_env(data: EnvUpdate) -> dict:
    """Обновляет .env файл с ключами."""
    save_env_vars(data.model_dump())
    await broadcast_log({
        "type": "info", "text": "Переменные окружения (.env) обновлены.",
        "sender": "system", "timestamp": "",
    })
    return {"status": "ok"}


# ============================================================
# Авторизация Telegram через веб-интерфейс
# ============================================================

class PhoneSubmit(BaseModel):
    phone: str

class CodeSubmit(BaseModel):
    code: str


@app.get("/auth/status")
async def auth_status() -> dict:
    """Возвращает текущее состояние авторизации."""
    is_auth = await telegram_client.is_user_authorized()
    return {
        "needs_phone": telegram_client.auth_manager.needs_phone,
        "needs_code": telegram_client.auth_manager.needs_code,
        "needs_2fa": False,  # будем определять по сообщению из лога
        "is_authorized": is_auth,
    }


@app.post("/auth/phone")
async def auth_phone(data: PhoneSubmit) -> dict:
    """Принимает номер телефона от пользователя."""
    phone = data.phone.strip()
    if not phone.startswith("+"):
        phone = "+" + phone

    submitted = telegram_client.auth_manager.submit_phone(phone)
    if submitted:
        await broadcast_log({
            "type": "info", "text": f"Номер телефона получен. Отправляю код...",
            "sender": "auth", "timestamp": "",
        })
        return {"status": "ok", "message": "Номер принят. Ожидайте код в Telegram."}
    else:
        return {"status": "error", "message": "Нет ожидающего запроса авторизации."}


@app.post("/auth/code")
async def auth_code(data: CodeSubmit) -> dict:
    """Принимает код подтверждения от пользователя."""
    code = data.code.strip()
    submitted = telegram_client.auth_manager.submit_code(code)
    if submitted:
        await broadcast_log({
            "type": "info", "text": "Код получен. Проверяю...",
            "sender": "auth", "timestamp": "",
        })
        return {"status": "ok", "message": "Код принят."}
    else:
        return {"status": "error", "message": "Нет ожидающего запроса кода."}


# ============================================================
# Тестирование AI API
# ============================================================

@app.post("/test-api")
async def test_api() -> dict:
    """Проверяет соединение с AI API (отправляет тестовый запрос)."""
    from app.ai_client import ai_client
    try:
        # Отправляем короткий тестовый запрос
        response = await ai_client.generate_response(
            message="Ответь одним словом: Привет",
            system_prompt="Ты — полезный ассистент. Отвечай максимально кратко.",
        )
        if response and len(response) > 0:
            return {
                "status": "ok",
                "message": f"✅ API работает! Ответ: {response[:100]}",
                "response": response[:200],
            }
        else:
            return {"status": "error", "message": "❌ API вернул пустой ответ."}
    except Exception as e:
        error_text = str(e)[:200]
        return {"status": "error", "message": f"❌ Ошибка: {error_text}"}


# ============================================================
# Управление агентом
# ============================================================
@app.post("/start")
async def start_agent() -> StatusResponse:
    if telegram_client.is_running():
        return StatusResponse(status="already_running", message="Агент уже запущен.")
    try:
        import asyncio
        asyncio.create_task(telegram_client.start_telegram_client())
        return StatusResponse(status="ok", message="Telegram-агент запускается...")
    except Exception as e:
        return StatusResponse(status="error", message=f"Ошибка запуска: {e}")


@app.post("/stop")
async def stop_agent() -> StatusResponse:
    if not telegram_client.is_running():
        return StatusResponse(status="not_running", message="Агент не запущен.")
    await telegram_client.stop_telegram_client()
    return StatusResponse(status="ok", message="Telegram-агент остановлен.")


@app.get("/status")
async def get_status() -> dict:
    return {
        "running": telegram_client.is_running(),
        "api_url": settings.OPENAI_BASE_URL,
        "model": settings.AI_MODEL,
        "api_format": settings.API_FORMAT,
    }


# ============================================================
# WebSocket
# ============================================================
@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket) -> None:
    await ws.accept()
    connected_ws.append(ws)
    try:
        await ws.send_json({
            "type": "info", "text": "WebSocket подключён.",
            "sender": "system", "timestamp": "",
        })
        while True:
            data = await ws.receive_text()
            try:
                msg = json.loads(data)
                if msg.get("type") == "ping":
                    await ws.send_json({"type": "pong"})
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"Ошибка WebSocket: {e}")
    finally:
        if ws in connected_ws:
            connected_ws.remove(ws)
