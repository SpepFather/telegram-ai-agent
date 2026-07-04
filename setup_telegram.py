#!/usr/bin/env python3
"""
Разовый скрипт авторизации в Telegram.
Запустить ОДИН РАЗ из консоли WSL:
  cd ~/telegram-ai-agent && source venv/bin/activate && python setup_telegram.py

После успешной авторизации сессия сохранится в bot_session.session,
и веб-панель сможет запускать агента без повторного ввода кода.
"""

import asyncio
import sys
from pathlib import Path

# Добавляем корень проекта в путь
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from telethon import TelegramClient
from app.config import settings


async def main():
    print("=" * 60)
    print("  🤖 Telegram AI Agent — Авторизация")
    print("=" * 60)

    # Проверяем наличие API-ключей
    if not settings.TELEGRAM_API_ID or not settings.TELEGRAM_API_HASH:
        print("\n❌ Ошибка: TELEGRAM_API_ID и TELEGRAM_API_HASH не настроены!")
        print("   Отредактируйте .env в корне проекта или")
        print("   заполните их через веб-интерфейс http://localhost:8000")
        return

    print(f"\n  API ID:   {settings.TELEGRAM_API_ID}")
    print(f"  API Hash: {settings.TELEGRAM_API_HASH[:6]}...")
    print(f"\n  Сессия будет сохранена в: bot_session.session\n")

    client = TelegramClient(
        str(BASE_DIR / "bot_session"),
        settings.TELEGRAM_API_ID,
        settings.TELEGRAM_API_HASH,
    )

    await client.connect()

    if await client.is_user_authorized():
        me = await client.get_me()
        print(f"✅ Уже авторизован как: {me.first_name} (id: {me.id})")
        print("   Сессия работает — веб-панель готова к использованию.")
        await client.disconnect()
        return

    print("🔄 Требуется авторизация. Введите номер телефона и код из Telegram.\n")
    
    try:
        await client.start()
        me = await client.get_me()
        print(f"\n✅ Успешно авторизован как: {me.first_name} (id: {me.id})")
        print("   Сессия сохранена. Теперь веб-панель может запускать агента.")
    except Exception as e:
        print(f"\n❌ Ошибка авторизации: {e}")
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
