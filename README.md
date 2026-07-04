# 🤖 Telegram AI Agent

Веб-панель управления AI-агентом в Telegram. Бот принимает сообщения от разрешённых контактов и отвечает через OpenAI-совместимый API (OpenModel AI, OpenAI и другие).

## 📋 Возможности

- 🌐 **Веб-интерфейс** — управление ботом через браузер (Bootstrap 5)
- 💬 **Telegram-бот** — приём и отправка сообщений через Telethon
- 🧠 **AI-ответы** — генерация через OpenAI-совместимый API
- ⚡ **WebSocket логи** — все события в реальном времени
- ⚙️ **Онлайн-редактор** — настройка config.json прямо в браузере
- 🔒 **Фильтр контактов** — отвечает только разрешённым пользователям

## 📂 Структура проекта

```
telegram-ai-agent/
├── app/
│   ├── __init__.py          # Пакет
│   ├── main.py              # FastAPI: эндпоинты, WebSocket
│   ├── telegram_client.py   # Telethon: подключение, обработка сообщений
│   ├── ai_client.py         # OpenAI-совместимый клиент
│   ├── config.py            # Загрузка .env и config.json
│   └── models.py            # Pydantic модели
├── static/
│   ├── index.html           # Главная страница
│   ├── style.css            # Стили (тёмная тема)
│   └── script.js            # Логика интерфейса
├── config.json              # Настройки (контакты, промпт)
├── .env                     # Секретные ключи (API)
├── requirements.txt         # Зависимости Python
├── run.py                   # Точка входа
└── README.md                # Этот файл
```

## 🚀 Установка и запуск

### 1. Клонируйте / создайте папку

```bash
cd ~/telegram-ai-agent
```

### 2. Создайте виртуальное окружение

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Установите зависимости

```bash
pip install -r requirements.txt
```

### 4. Настройте переменные окружения

Отредактируйте `.env` и укажите ваши ключи:

```env
TELEGRAM_API_ID=12345678          # С https://my.telegram.org/apps
TELEGRAM_API_HASH=abcdef123456   # С https://my.telegram.org/apps
OPENAI_API_KEY=sk-...            # Ваш API-ключ
OPENAI_BASE_URL=https://api.openmodel.ai/v1
AI_MODEL=gpt-4o
```

### 5. Настройте config.json (через веб-интерфейс или вручную)

```json
{
  "allowed_contacts": ["+79001234567", "username"],
  "system_prompt": "Ты — дружелюбный собеседник."
}
```

### 6. Запустите сервер

```bash
python run.py
```

### 7. Откройте в браузере

- **Из Windows**: `http://localhost:8000`
- **Из WSL**: `http://127.0.0.1:8000`

## 🔧 Как это работает

1. **Запуск** — нажмите «Запустить агента» в веб-панели.
2. **Подключение** — Telethon подключается к Telegram (первый раз потребуется код из Telegram).
3. **Получение сообщений** — бот слушает входящие сообщения.
4. **Фильтрация** — проверяет, есть ли отправитель в `allowed_contacts`.
5. **AI-ответ** — отправляет сообщение в OpenAI API с системным промптом.
6. **Отправка** — ответ возвращается в чат Telegram.

## ⚠️ Важно

- **Первый запуск Telegram**: при первом подключении Telethon запросит номер телефона и код авторизации. Сессия сохранится в файл `bot_session.session`.
- **Безопасность**: файл `.env` содержит секреты — не коммитьте его в git.
- **Контакты**: если `allowed_contacts` пустой, бот будет отвечать всем (для отладки).

## 🛠 Технологии

- **Python 3.12+**
- **FastAPI** — веб-фреймворк
- **Telethon** — Telegram MTProto клиент
- **OpenAI SDK** — AI-генерация (поддержка кастомного base_url)
- **Bootstrap 5** — стили интерфейса
- **WebSocket** — логи в реальном времени
