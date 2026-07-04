#!/usr/bin/env python3
"""
Точка входа: запуск uvicorn-сервера.
Автоматически открывает браузер при локальном запуске.
"""

import os
import sys
import subprocess
import threading
import time
import webbrowser
from pathlib import Path

# Добавляем корень проекта в Python path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))


def open_browser(url: str, delay: float = 1.5) -> None:
    """Открывает браузер через указанную задержку."""
    time.sleep(delay)
    print(f"\n🌐 Открываю браузер: {url}")
    webbrowser.open(url)


def main() -> None:
    """Запускает uvicorn-сервер."""
    host = "0.0.0.0"
    port = 8000
    url = f"http://127.0.0.1:{port}"

    print("=" * 60)
    print("  🤖 Telegram AI Agent — Веб-панель управления")
    print("=" * 60)
    print(f"\n  🌐 Локальный доступ:   {url}")
    print(f"  🌐 Доступ из Windows: http://localhost:{port}")
    print(f"  📡 WebSocket:        ws://127.0.0.1:{port}/ws")
    print(f"\n  Нажмите Ctrl+C для остановки.\n")

    # Пытаемся автоматически открыть браузер
    try:
        browser_thread = threading.Thread(
            target=open_browser,
            args=(url,),
            daemon=True,
        )
        browser_thread.start()
    except Exception:
        pass  # В WSL webbrowser может не работать — это нормально

    # Импортируем здесь, чтобы uvicorn не требовался при импорте модуля
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()
