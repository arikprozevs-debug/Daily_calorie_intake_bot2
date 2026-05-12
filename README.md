Telegram-бот для подсчёта калорий и КБЖУ с интерактивным меню.

## Функции

- 📊 Сводка калорий за день с прогресс-баром
- ➕ Добавление продуктов по названию (17+ продуктов в базе)
- ⚖️ Выбор граммовки (быстрые кнопки + своё значение)
- 🎯 Настраиваемая дневная цель калорий
- 🗑 Сброс дневника за день
- 🌐 Кнопка открытия Web App (если задан WEBAPP_URL)

---

## 🚀 Деплой на Railway (бесплатно)

### Шаг 1 — Получить токен бота

1. Открой Telegram, найди **@BotFather**
2. Отправь `/newbot`
3. Придумай имя и username для бота
4. Скопируй токен вида `1234567890:ABCdef...`

### Шаг 2 — Залить код на GitHub

1. Зайди на [github.com](https://github.com) → New repository
2. Назови репозиторий `calorie-bot`
3. Загрузи файлы: `bot.py`, `requirements.txt`, `Procfile`

### Шаг 3 — Деплой на Railway

1. Зайди на [railway.app](https://railway.app)
2. Нажми **New Project → Deploy from GitHub repo**
3. Выбери свой репозиторий `calorie-bot`
4. Перейди в **Variables** и добавь:
   ```
   BOT_TOKEN = твой_токен_от_BotFather
   ```
5. Railway автоматически запустит бота

### Шаг 4 (опционально) — Подключить Web App

Если хочешь кнопку с графическим интерфейсом:
1. Задеплой папку `webapp/` на [Vercel](https://vercel.com) или [Netlify](https://netlify.com)
2. Добавь переменную в Railway:
   ```
   WEBAPP_URL = https://твой-сайт.vercel.app
   ```

---

## 🚀 Деплой на Render (альтернатива)

1. Зайди на [render.com](https://render.com)
2. New → **Background Worker**
3. Подключи GitHub репозиторий
4. Build Command: `pip install -r requirements.txt`
5. Start Command: `python bot.py`
6. В Environment Variables добавь `BOT_TOKEN`

---

## Локальный запуск (для теста)

```bash
pip install -r requirements.txt
BOT_TOKEN="твой_токен" python bot.py
```

---

## Структура проекта

```
calorie_bot/
├── bot.py            # Основной код бота
├── requirements.txt  # Зависимости Python
├── Procfile          # Команда запуска для Railway/Heroku
└── README.md         # Эта инструкция
```

---

## Расширение базы продуктов

В `bot.py` найди словарь `FOODS` и добавляй продукты в формате:
```python
"название": {"cal": 000, "p": 0.0, "f": 0.0, "c": 0.0},
```
Все значения — на 100 граммов продукта.
