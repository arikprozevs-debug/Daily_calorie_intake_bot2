import os
import json
import logging
from datetime import date
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
WEBAPP_URL = os.environ.get("WEBAPP_URL", "https://your-app.vercel.app")

# ── База продуктов (на 100г) ──────────────────────────────────────────────────
FOODS = {
    "куриная грудка": {"cal": 165, "p": 31.0, "f": 3.6, "c": 0.0},
    "овсянка":        {"cal": 68,  "p": 2.4,  "f": 1.4,  "c": 12.0},
    "яйцо":           {"cal": 155, "p": 13.0, "f": 11.0, "c": 1.1},
    "греческий йогурт":{"cal": 59, "p": 10.0, "f": 0.4,  "c": 3.6},
    "рис":            {"cal": 130, "p": 2.7,  "f": 0.3,  "c": 28.0},
    "гречка":         {"cal": 92,  "p": 3.5,  "f": 0.6,  "c": 17.0},
    "банан":          {"cal": 89,  "p": 1.1,  "f": 0.3,  "c": 23.0},
    "творог 5%":      {"cal": 121, "p": 17.0, "f": 5.0,  "c": 2.7},
    "лосось":         {"cal": 208, "p": 20.0, "f": 13.0, "c": 0.0},
    "хлеб ц/з":       {"cal": 247, "p": 9.0,  "f": 3.4,  "c": 41.0},
    "авокадо":        {"cal": 160, "p": 2.0,  "f": 15.0, "c": 9.0},
    "молоко 2.5%":    {"cal": 52,  "p": 2.9,  "f": 2.5,  "c": 4.7},
    "картофель":      {"cal": 86,  "p": 2.0,  "f": 0.1,  "c": 20.0},
    "огурец":         {"cal": 15,  "p": 0.7,  "f": 0.1,  "c": 2.8},
    "помидор":        {"cal": 20,  "p": 0.9,  "f": 0.2,  "c": 3.9},
    "арахисовая паста":{"cal": 588,"p": 25.0, "f": 50.0, "c": 20.0},
    "миндаль":        {"cal": 579, "p": 21.0, "f": 50.0, "c": 22.0},
}

# ── Хранилище (в памяти, для продакшна замените на БД) ───────────────────────
user_data: dict = {}   # { user_id: { "goal": 2000, "log": { "YYYY-MM-DD": [...] } } }

def get_user(uid: int) -> dict:
    if uid not in user_data:
        user_data[uid] = {"goal": 2000, "log": {}}
    return user_data[uid]

def today() -> str:
    return date.today().isoformat()

def day_log(uid: int) -> list:
    u = get_user(uid)
    return u["log"].setdefault(today(), [])

def day_totals(uid: int) -> dict:
    cal = p = f = c = 0
    for entry in day_log(uid):
        r = entry["grams"] / 100
        cal += entry["cal_per100"] * r
        p   += entry["p_per100"]   * r
        f   += entry["f_per100"]   * r
        c   += entry["c_per100"]   * r
    return {"cal": round(cal), "p": round(p, 1), "f": round(f, 1), "c": round(c, 1)}

# ── Клавиатуры ────────────────────────────────────────────────────────────────
def main_keyboard(uid: int) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton("📊 Сводка за сегодня", callback_data="summary")],
        [InlineKeyboardButton("➕ Добавить еду",       callback_data="add_food")],
        [InlineKeyboardButton("🗑 Очистить день",      callback_data="clear_day")],
        [InlineKeyboardButton("🎯 Изменить цель",      callback_data="set_goal")],
    ]
    if WEBAPP_URL and WEBAPP_URL != "https://your-app.vercel.app":
        buttons.insert(0, [
            InlineKeyboardButton(
                "🌐 Открыть трекер",
                web_app=WebAppInfo(url=WEBAPP_URL)
            )
        ])
    return InlineKeyboardMarkup(buttons)

def food_keyboard(query: str) -> InlineKeyboardMarkup:
    matches = [name for name in FOODS if query.lower() in name][:8]
    rows = [[InlineKeyboardButton(name.capitalize(), callback_data=f"pick_{name}")]
            for name in matches]
    rows.append([InlineKeyboardButton("❌ Отмена", callback_data="cancel")])
    return InlineKeyboardMarkup(rows)

def grams_keyboard(food_name: str) -> InlineKeyboardMarkup:
    portions = [50, 100, 150, 200, 300]
    rows = [
        [InlineKeyboardButton(f"{g} г", callback_data=f"grams_{food_name}_{g}")
         for g in portions[:3]],
        [InlineKeyboardButton(f"{g} г", callback_data=f"grams_{food_name}_{g}")
         for g in portions[3:]],
        [InlineKeyboardButton("✏️ Своё кол-во", callback_data=f"custom_{food_name}")],
        [InlineKeyboardButton("❌ Отмена", callback_data="cancel")],
    ]
    return InlineKeyboardMarkup(rows)

# ── Форматирование ────────────────────────────────────────────────────────────
def summary_text(uid: int) -> str:
    t = day_totals(uid)
    goal = get_user(uid)["goal"]
    rem = goal - t["cal"]
    bar_len = 10
    filled = min(round(t["cal"] / goal * bar_len), bar_len)
    bar = "█" * filled + "░" * (bar_len - filled)

    lines = [
        f"📅 *{today()}*",
        f"",
        f"🔥 Калории: *{t['cal']}* / {goal} ккал",
        f"`[{bar}]`",
        f"{'✅ Цель достигнута!' if rem <= 0 else f'👉 Осталось: {rem} ккал'}",
        f"",
        f"🥩 Белки:   *{t['p']}* г",
        f"🧈 Жиры:    *{t['f']}* г",
        f"🍞 Углеводы: *{t['c']}* г",
        f"",
    ]

    entries = day_log(uid)
    if entries:
        lines.append("*Съедено сегодня:*")
        for e in entries:
            ec = round(e["cal_per100"] * e["grams"] / 100)
            lines.append(f"• {e['name'].capitalize()} {e['grams']}г — {ec} ккал")
    else:
        lines.append("_Ещё ничего не добавлено_")

    return "\n".join(lines)

# ── Handlers ──────────────────────────────────────────────────────────────────
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    name = update.effective_user.first_name or "друг"
    get_user(uid)
    await update.message.reply_text(
        f"Привет, {name}! 👋\n\n"
        f"Я помогу тебе считать калории и следить за питанием.\n\n"
        f"Выбери действие:",
        reply_markup=main_keyboard(uid),
        parse_mode="Markdown"
    )

async def button_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    data = query.data

    # ── Сводка ────────────────────────────────────────────────────────────────
    if data == "summary":
        await query.edit_message_text(
            summary_text(uid),
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🏠 Главное меню", callback_data="menu")
            ]]),
            parse_mode="Markdown"
        )

    # ── Главное меню ──────────────────────────────────────────────────────────
    elif data == "menu":
        await query.edit_message_text(
            "Выбери действие:",
            reply_markup=main_keyboard(uid)
        )

    # ── Добавить еду ──────────────────────────────────────────────────────────
    elif data == "add_food":
        ctx.user_data["state"] = "waiting_food"
        await query.edit_message_text(
            "🔍 Введи название продукта (например: *курица*, *рис*, *банан*):",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ Отмена", callback_data="cancel")
            ]])
        )

    # ── Выбор продукта из списка ──────────────────────────────────────────────
    elif data.startswith("pick_"):
        food_name = data[5:]
        await query.edit_message_text(
            f"*{food_name.capitalize()}* — {FOODS[food_name]['cal']} ккал/100г\n\n"
            f"Сколько граммов?",
            parse_mode="Markdown",
            reply_markup=grams_keyboard(food_name)
        )

    # ── Выбор граммов ─────────────────────────────────────────────────────────
    elif data.startswith("grams_"):
        _, food_name, grams_str = data.split("_", 2)
        grams = int(grams_str)
        _add_entry(uid, food_name, grams)
        ec = round(FOODS[food_name]["cal"] * grams / 100)
        await query.edit_message_text(
            f"✅ Добавлено: *{food_name.capitalize()}* {grams}г → {ec} ккал",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ Ещё", callback_data="add_food")],
                [InlineKeyboardButton("📊 Сводка", callback_data="summary")],
                [InlineKeyboardButton("🏠 Меню", callback_data="menu")],
            ])
        )

    # ── Своё кол-во ───────────────────────────────────────────────────────────
    elif data.startswith("custom_"):
        food_name = data[7:]
        ctx.user_data["state"] = "waiting_grams"
        ctx.user_data["food_name"] = food_name
        await query.edit_message_text(
            f"*{food_name.capitalize()}*\n\nВведи количество граммов (число):",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ Отмена", callback_data="cancel")
            ]])
        )

    # ── Очистить день ─────────────────────────────────────────────────────────
    elif data == "clear_day":
        get_user(uid)["log"][today()] = []
        await query.edit_message_text(
            "🗑 Дневник за сегодня очищен.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🏠 Главное меню", callback_data="menu")
            ]])
        )

    # ── Изменить цель ─────────────────────────────────────────────────────────
    elif data == "set_goal":
        ctx.user_data["state"] = "waiting_goal"
        await query.edit_message_text(
            f"🎯 Текущая цель: *{get_user(uid)['goal']} ккал*\n\n"
            f"Введи новую цель (например: 1800):",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ Отмена", callback_data="cancel")
            ]])
        )

    # ── Отмена ────────────────────────────────────────────────────────────────
    elif data == "cancel":
        ctx.user_data.pop("state", None)
        ctx.user_data.pop("food_name", None)
        await query.edit_message_text(
            "Выбери действие:",
            reply_markup=main_keyboard(uid)
        )

async def text_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = update.message.text.strip()
    state = ctx.user_data.get("state")

    # ── Ввод продукта ─────────────────────────────────────────────────────────
    if state == "waiting_food":
        ctx.user_data.pop("state", None)
        matches = [name for name in FOODS if text.lower() in name]
        if not matches:
            await update.message.reply_text(
                f"❌ Продукт «{text}» не найден.\n\nПопробуй: курица, рис, гречка, яйцо, банан...",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔍 Искать снова", callback_data="add_food")],
                    [InlineKeyboardButton("🏠 Меню", callback_data="menu")],
                ])
            )
        else:
            await update.message.reply_text(
                f"Найдено {len(matches)} продукт(а). Выбери:",
                reply_markup=food_keyboard(text.lower())
            )

    # ── Ввод граммов ──────────────────────────────────────────────────────────
    elif state == "waiting_grams":
        food_name = ctx.user_data.get("food_name")
        ctx.user_data.pop("state", None)
        ctx.user_data.pop("food_name", None)
        try:
            grams = int(text)
            if grams <= 0: raise ValueError
            _add_entry(uid, food_name, grams)
            ec = round(FOODS[food_name]["cal"] * grams / 100)
            await update.message.reply_text(
                f"✅ Добавлено: *{food_name.capitalize()}* {grams}г → {ec} ккал",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("➕ Ещё", callback_data="add_food")],
                    [InlineKeyboardButton("📊 Сводка", callback_data="summary")],
                    [InlineKeyboardButton("🏠 Меню", callback_data="menu")],
                ])
            )
        except (ValueError, TypeError):
            await update.message.reply_text(
                "⚠️ Введи целое число (например: 150)",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("❌ Отмена", callback_data="cancel")
                ]])
            )

    # ── Ввод цели ─────────────────────────────────────────────────────────────
    elif state == "waiting_goal":
        ctx.user_data.pop("state", None)
        try:
            goal = int(text)
            if goal < 500 or goal > 10000: raise ValueError
            get_user(uid)["goal"] = goal
            await update.message.reply_text(
                f"✅ Цель установлена: *{goal} ккал/день*",
                parse_mode="Markdown",
                reply_markup=main_keyboard(uid)
            )
        except (ValueError, TypeError):
            await update.message.reply_text(
                "⚠️ Введи число от 500 до 10000 (например: 1800)",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("❌ Отмена", callback_data="cancel")
                ]])
            )
    else:
        await update.message.reply_text(
            "Привет! Используй меню 👇",
            reply_markup=main_keyboard(uid)
        )

def _add_entry(uid: int, food_name: str, grams: int):
    food = FOODS[food_name]
    day_log(uid).append({
        "name": food_name,
        "grams": grams,
        "cal_per100": food["cal"],
        "p_per100":   food["p"],
        "f_per100":   food["f"],
        "c_per100":   food["c"],
    })

# ── Запуск ────────────────────────────────────────────────────────────────────
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    logger.info("Бот запущен...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
