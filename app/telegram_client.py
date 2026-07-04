"""
Telegram-клиент на базе Telethon.
Обрабатывает входящие сообщения от разрешённых контактов,
генерирует AI-ответы и отправляет их обратно.
Поддерживает контекст диалога, настраиваемую задержку и авторизацию через веб.
"""

import asyncio
import logging
import random
from collections import defaultdict
from datetime import datetime
from typing import Callable

from telethon import TelegramClient, events, errors as tg_errors

from app.ai_client import ai_client
from app.config import settings, load_config_json, BASE_DIR

logger = logging.getLogger(__name__)

# ============================================================
# Conversation Memory
# ============================================================

class ConversationMemory:
    """Хранит историю сообщений по чатам."""

    def __init__(self):
        self._store: dict[int, list[dict]] = defaultdict(list)

    def add_message(self, chat_id: int, role: str, content: str) -> None:
        self._store[chat_id].append({"role": role, "content": content})

    def get_history(self, chat_id: int, max_messages: int = 6) -> list[dict]:
        return self._store[chat_id][-max_messages:]

    def clear(self, chat_id: int | None = None) -> None:
        if chat_id:
            self._store.pop(chat_id, None)
        else:
            self._store.clear()

memory = ConversationMemory()

# ============================================================
# Auth Manager
# ============================================================

class AuthManager:
    """Управляет авторизацией через веб-интерфейс."""

    def __init__(self):
        self._phone_event: asyncio.Event | None = None
        self._code_event: asyncio.Event | None = None
        self._phone: str | None = None
        self._code: str | None = None
        self._needs_phone = False
        self._needs_code = False

    @property
    def needs_phone(self) -> bool: return self._needs_phone

    @property
    def needs_code(self) -> bool: return self._needs_code

    def submit_phone(self, phone: str) -> bool:
        if not self._phone_event: return False
        self._phone = phone.strip()
        self._phone_event.set()
        return True

    def submit_code(self, code: str) -> bool:
        if not self._code_event: return False
        self._code = code.strip()
        self._code_event.set()
        return True

    def reset(self) -> None:
        self._phone_event = None
        self._code_event = None
        self._phone = None
        self._code = None
        self._needs_phone = False
        self._needs_code = False

    async def wait_for_phone(self, timeout: int = 300) -> str | None:
        self._needs_phone = True
        self._phone_event = asyncio.Event()
        self._phone = None
        try:
            await asyncio.wait_for(self._phone_event.wait(), timeout=timeout)
            self._needs_phone = False
            return self._phone
        except asyncio.TimeoutError:
            self._needs_phone = False
            return None
        finally:
            self._phone_event = None

    async def wait_for_code(self, timeout: int = 300) -> str | None:
        self._needs_code = True
        self._code_event = asyncio.Event()
        self._code = None
        try:
            await asyncio.wait_for(self._code_event.wait(), timeout=timeout)
            self._needs_code = False
            return self._code
        except asyncio.TimeoutError:
            self._needs_code = False
            return None
        finally:
            self._code_event = None


# ============================================================
# Глобальное состояние
# ============================================================

auth_manager = AuthManager()
telegram_client: TelegramClient | None = None
_client_task: asyncio.Task | None = None
_ws_log_callback: Callable | None = None


def set_ws_log_callback(callback: Callable) -> None:
    global _ws_log_callback
    _ws_log_callback = callback


async def _send_log(log_type: str, text: str, sender: str = "") -> None:
    timestamp = datetime.now().strftime("%H:%M:%S")
    entry = {"type": log_type, "text": text, "sender": sender, "timestamp": timestamp}
    if _ws_log_callback:
        try:
            await _ws_log_callback(entry)
        except Exception:
            pass
    if log_type == "error":
        logger.error(f"[{timestamp}] {text}")
    else:
        logger.info(f"[{timestamp}] {text}")


def _contact_matches(contact_label: str, sender_id: str, allowed: list) -> bool:
    if not allowed:
        return True
    contact_lower = contact_label.lower()
    for item in allowed:
        item_lower = str(item).lower().strip()
        if item_lower in contact_lower or item_lower == sender_id:
            return True
    return False


# ============================================================
# Обработчик входящих сообщений
# ============================================================

async def _handle_new_message(event: events.NewMessage.Event) -> None:
    message = event.message
    sender = await event.get_sender()
    chat_id = event.chat_id
    msg_text = message.text or ""
    now = datetime.now()

    sender_id = str(sender.id) if sender else "Unknown"
    sender_name = getattr(sender, "first_name", "") or ""
    sender_phone = getattr(sender, "phone", "") or ""
    sender_username = getattr(sender, "username", "") or ""
    contact_label = sender_username or sender_phone or f"{sender_name} (id:{sender_id})"

    text_preview = msg_text[:200]
    await _send_log("message", f"Новое сообщение от {contact_label}: {text_preview}", sender=contact_label)

    config = load_config_json()
    allowed = config.get("allowed_contacts", [])
    if not _contact_matches(contact_label, sender_id, allowed):
        await _send_log("info", f"Контакт {contact_label} не в разрешённом списке — игнорируем.")
        return

    system_prompt = config.get("system_prompt", "Ты — дружелюбный собеседник.")
    min_delay = max(0.0, config.get("min_delay", 1.0))
    max_delay = max(min_delay + 0.5, config.get("max_delay", 3.0))
    context_enabled = config.get("context_enabled", True)
    context_max = min(50, max(1, config.get("context_messages", 6)))

    try:
        # Сохраняем сообщение пользователя в память
        if context_enabled:
            memory.add_message(chat_id, "user", msg_text)
            # Берём историю из памяти
            history = memory.get_history(chat_id, context_max)
            # Формируем сообщения для AI
            messages = [{"role": "system", "content": system_prompt}]
            for m in history:
                messages.append({"role": m["role"], "content": m["content"]})
        else:
            messages = None

        # Задержка "печатает..."
        delay = random.uniform(min_delay, max_delay)
        await _send_log("info", f"⏳ Пауза {delay:.1f}с...")
        await asyncio.sleep(delay)

        await _send_log("info", "Генерирую ответ через AI...")
        ai_response = await ai_client.generate_response(
            message=msg_text,
            system_prompt=system_prompt,
            messages=messages,  # если None, ai_client использует простой формат
        )

        # Сохраняем ответ AI в память
        if context_enabled:
            memory.add_message(chat_id, "assistant", ai_response)

        # Отправляем обычным сообщением (не reply)
        await telegram_client.send_message(chat_id, ai_response)

        await _send_log("reply", f"✅ Ответ отправлен {contact_label}: {ai_response[:200]}", sender="AI")

    except Exception as e:
        await _send_log("error", f"Ошибка обработки сообщения: {e}")


# ============================================================
# Запуск / остановка
# ============================================================

async def start_telegram_client() -> None:
    global telegram_client, _client_task

    if telegram_client and telegram_client.is_connected():
        await _send_log("info", "Telegram-клиент уже запущен.")
        return

    if not settings.TELEGRAM_API_ID or not settings.TELEGRAM_API_HASH:
        await _send_log("error", "TELEGRAM_API_ID и TELEGRAM_API_HASH не настроены в .env!")
        return

    await _send_log("info", "Запуск Telegram-клиента...")

    telegram_client = TelegramClient(
        str(BASE_DIR / "bot_session"),
        settings.TELEGRAM_API_ID,
        settings.TELEGRAM_API_HASH,
    )

    try:
        await telegram_client.connect()

        if not await telegram_client.is_user_authorized():
            await _web_auth_flow()
            if not await telegram_client.is_user_authorized():
                return

        me = await telegram_client.get_me()
        me_name = me.first_name or "Unknown"
        await _send_log("info", f"Подключён как: {me_name} (id: {me.id})")

        telegram_client.add_event_handler(_handle_new_message, events.NewMessage(incoming=True))

        _client_task = asyncio.create_task(
            telegram_client.run_until_disconnected(),
            name="telegram_client",
        )
        await _send_log("info", "Telegram-агент запущен и слушает сообщения!")

    except Exception as e:
        await _send_log("error", f"Ошибка запуска Telegram-клиента: {e}")
        telegram_client = None


async def _web_auth_flow() -> None:
    auth_manager.reset()
    try:
        await _send_log("info", "Требуется номер телефона. Введите в модальном окне.")
        phone = await auth_manager.wait_for_phone(timeout=300)
        if phone is None:
            await _send_log("error", "Таймаут ввода номера телефона.")
            auth_manager.reset()
            return

        await _send_log("info", "Отправляю код подтверждения в Telegram...")
        sent = await telegram_client.send_code_request(phone)
        phone_code_hash = sent.phone_code_hash
        await _send_log("info", "Код отправлен в Telegram. Введите код.")

        code = await auth_manager.wait_for_code(timeout=300)
        if code is None:
            await _send_log("error", "Таймаут ввода кода.")
            auth_manager.reset()
            return

        await _send_log("info", "Проверяю код...", sender="system")
        try:
            await telegram_client.sign_in(phone, code, phone_code_hash=phone_code_hash)
        except tg_errors.PhoneCodeInvalidError:
            await _send_log("error", "Неверный код. Попробуйте снова.")
            code = await auth_manager.wait_for_code(timeout=120)
            if code is None:
                await _send_log("error", "Таймаут повторного ввода кода.")
                auth_manager.reset()
                return
            await telegram_client.sign_in(phone, code, phone_code_hash=phone_code_hash)
        except tg_errors.SessionPasswordNeededError:
            await _send_log("info", "Требуется пароль двухфакторной аутентификации.")
            password = await auth_manager.wait_for_code(timeout=120)
            if password is None:
                await _send_log("error", "Таймаут ввода пароля.")
                auth_manager.reset()
                return
            await telegram_client.sign_in(password=password)

        auth_manager.reset()
        me = await telegram_client.get_me()
        await _send_log("info", f"✅ Авторизация успешна! Добро пожаловать, {me.first_name}.")

    except Exception as e:
        await _send_log("error", f"Ошибка авторизации: {e}")
        auth_manager.reset()


async def stop_telegram_client() -> None:
    global telegram_client, _client_task
    if not telegram_client or not telegram_client.is_connected():
        await _send_log("info", "Telegram-клиент не запущен.")
        return
    await _send_log("info", "Остановка Telegram-клиента...")
    try:
        if _client_task and not _client_task.done():
            _client_task.cancel()
            try:
                await _client_task
            except asyncio.CancelledError:
                pass
            _client_task = None
        await telegram_client.disconnect()
        await _send_log("info", "Telegram-агент остановлен.")
    except Exception as e:
        await _send_log("error", f"Ошибка остановки клиента: {e}")


def is_running() -> bool:
    return (telegram_client is not None and telegram_client.is_connected()
            and not auth_manager.needs_phone and not auth_manager.needs_code)


async def is_user_authorized() -> bool:
    if not telegram_client or not telegram_client.is_connected():
        return False
    return await telegram_client.is_user_authorized()
