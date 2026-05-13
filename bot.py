import os
import logging
import aiohttp
from datetime import date
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "8743418563:AAE1POmWzDtJxuXXD-XguEbEpaeOD9Xt8CI")
WEBAPP_URL = os.environ.get("WEBAPP_URL", "")

# ── Локальная база (запасная) ─────────────────────────────────────────────────
LOCAL_FOODS = {
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
    "индейка":        {"cal": 189, "p": 29.0, "f": 7.0,  "c": 0.0},
    "говядина":       {"cal": 250, "p": 26.0, "f": 15.0, "c": 0.0},
    "макароны":       {"cal": 138, "p": 4.9,  "f": 0.9,  "c": 28.0},
    "апельсин":       {"cal": 47,  "p": 0.9,  "f": 0.2,  "c": 11.0},
    "яблоко":         {"cal": 52,  "p": 0.3,  "f": 0.2,  "c": 14.0},
    "брокколи":       {"cal": 34,  "p": 2.8,  "f": 0.4,  "c": 6.6},
    "миндаль":        {"cal": 579, "p": 21.0, "f": 50.0, "c": 22.0},
    "кефир 1%":       {"cal": 40,  "p": 3.3,  "f": 1.0,  "c": 4.0},
    "тунец":          {"cal": 96,  "p": 21.5, "f": 0.7,  "c": 0.0},
    "свинина":        {"cal": 316, "p": 16.0, "f": 28.0, "c": 0.0},
    "шпинат":         {"cal": 23,  "p": 2.9,  "f": 0.4,  "c": 2.0},
    "клубника":       {"cal": 32,  "p": 0.7,  "f": 0.3,  "c": 7.7},
    "арахисовая паста":{"cal": 588,"p": 25.0, "f": 50.0, "c": 20.0},
}

# ── Хранилище ─────────────────────────────────────────────────────────────────
user_data: dict = {}

def get_user(uid: int) -> dict:
    if uid not in user_data:
        user_data[uid] = {"goal": 2000, "log": {}}
    return user_data[uid]

def today() -> str:
    return date.today().isoformat()

def day_log(uid: int) -> list:
    return get_user(uid)["log"].setdefault(today(), [])

def day_totals(uid: int) -> dict:
    cal = p = f = c = 0
    for e in day_log(uid):
        r = e["grams"] / 100
        cal += e["cal_per100"] * r
        p   += e["p_per100"]   * r
        f   += e["f_per100"]   * r
        c   += e["c_per100"]   * r
    return {"cal": round(cal), "p": round(p,1), "f": round(f,1), "c": round(c,1)}

# ── Open Food Facts поиск ─────────────────────────────────────────────────────
async def search_openfoodfacts(query: str) -> list:
    url = "https://world.openfoodfacts.org/cgi/search.pl"
    params = {
        "search_terms": query,
        "search_simple": 1,
        "action": "process",
        "json": 1,
        "page_size": 6,
        "fields": "product_name,nutriments,brands",
        "sort_by": "unique_scans_n",
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                data = await resp.json()
                results = []
                for p in data.get("products", []):
                    n = p.get("nutriments", {})
                    cal = n.get("energy-kcal_100g") or n.get("energy_100g", 0)
                    if not cal:
                        continue
                    name = p.get("product_name", "").strip()
                    brand = p.get("brands", "").split(",")[0].strip()
                    if not name:
                        continue
                    display = f"{name} ({brand})" if brand else name
                    results.append({
                        "name": display[:50],
                        "cal": round(float(cal)),
                        "p":   round(float(n.get("proteins_100g", 0)), 1),
                        "f":   round(float(n.get("fat_100g", 0)), 1),
                        "c":   round(float(n.get("carbohydrates_100g", 0)), 1),
                    })
                return results[:6]
    except Exception as e:
        logger.warning(f"OpenFoodFacts error: {e}")
        return []

def search_local(query: str) -> list:
    q = query.lower().strip()
    return [
        {"name": k.capitalize(), "cal": v["cal"], "p": v["p"], "f": v["f"], "c": v["c"]}
        for k, v in LOCAL_FOODS.items() if q in k
    ][:6]

# ── Клавиатуры ────────────────────────────────────────────────────────────────
def main_keyboard(uid: int) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton("📊 Сводка за сегодня", callback_data="summary")],
        [InlineKeyboardButton("➕ Добавить еду",       callback_data="add_food")],
        [InlineKeyboardButton("🗑 Очистить день",      callback_data="clear_day")],
        [InlineKeyboardButton("🎯 Изменить цель",      callback_data="set_goal")],
    ]
    if WEBAPP_URL:
        buttons.insert(0, [InlineKeyboardButton("🌐 Открыть трекер", web_app=WebAppInfo(url=WEBAPP_URL))])
    return InlineKeyboardMarkup(buttons)

def results_keyboard(results: list, source: str = "") -> InlineKeyboardMarkup:
    rows = []
    for i, food in enumerate(results):
        label = f"{food['name'][:28]} · {food['cal']} ккал"
        rows.append([InlineKeyboardButton(label, callback_data=f"pick_{i}")])
    rows.append([InlineKeyboardButton("🔍 Искать снова", callback_data="add_food")])
    rows.append([InlineKeyboardButton("❌ Отмена", callback_data="cancel")])
    return InlineKeyboardMarkup(rows)

def grams_keyboard(idx: int) -> InlineKeyboardMarkup:
    portions = [50, 100, 150, 200, 300]
    rows = [
        [InlineKeyboardButton(f"{g} г", callback_data=f"grams_{idx}_{g}") for g in portions[:3]],
        [InlineKeyboardButton(f"{g} г", callback_data=f"grams_{idx}_{g}") for g in portions[3:]],
        [InlineKeyboardButton("✏️ Своё количество", callback_data=f"custom_{idx}")],
        [InlineKeyboardButton("🔙 Назад", callback_data="add_food")],
    ]
    return InlineKeyboardMarkup(rows)

def meal_keyboard() -> InlineKeyboardMarkup:
    meals = [("🌅 Завтрак","breakfast"),("☀️ Обед","lunch"),("🌙 Ужин","dinner"),("🍎 Перекус","snack")]
    return InlineKeyboardMarkup([[InlineKeyboardButton(n, callback_data=f"meal_{id}")] for n, id in meals])

# ── Форматирование сводки ─────────────────────────────────────────────────────
def summary_text(uid: int) -> str:
    t = day_totals(uid)
    goal = get_user(uid)["goal"]
    rem = goal - t["cal"]
    filled = min(round(t["cal"] / goal * 10), 10)
    bar = "█" * filled + "░" * (10 - filled)
    lines = [
        f"📅 *{today()}*\n",
        f"🔥 Калории: *{t['cal']}* / {goal} ккал",
        f"`[{bar}]`",
        f"{'✅ Цель достигнута!' if rem <= 0 else f'👉 Осталось: {rem} ккал'}\n",
        f"🥩 Белки:    *{t['p']}* г",
        f"🧈 Жиры:     *{t['f']}* г",
        f"🍞 Углеводы: *{t['c']}* г\n",
    ]
    entries = day_log(uid)
    if entries:
        lines.append("*Съедено сегодня:*")
        for e in entries:
            ec = round(e["cal_per100"] * e["grams"] / 100)
            lines.append(f"• {e['name']} {e['grams']}г — {ec} ккал")
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
        f"Я помогу считать калории и КБЖУ.\n\n"
        f"Могу искать продукты в базе из *3 миллионов* позиций 🌍",
        reply_markup=main_keyboard(uid),
        parse_mode="Markdown"
    )

async def button_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    data = query.data

    if data == "summary":
        await query.edit_message_text(
            summary_text(uid),
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Меню", callback_data="menu")]]),
            parse_mode="Markdown"
        )

    elif data == "menu":
        await query.edit_message_text("Выбери действие:", reply_markup=main_keyboard(uid))

    elif data == "add_food":
        ctx.user_data["state"] = "waiting_food"
        ctx.user_data.pop("search_results", None)
        await query.edit_message_text(
            "🔍 *Поиск продукта*\n\n"
            "Введи название на русском или английском:\n"
            "_Например: гречка, apple, творог, chicken_",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data="cancel")]])
        )

    elif data.startswith("pick_"):
        idx = int(data[5:])
        results = ctx.user_data.get("search_results", [])
        if idx < len(results):
            ctx.user_data["picked_food"] = results[idx]
            food = results[idx]
            # Спросить приём пищи
            ctx.user_data["state"] = "waiting_meal"
            await query.edit_message_text(
                f"*{food['name']}*\n"
                f"🔥 {food['cal']} ккал · Б {food['p']}г · Ж {food['f']}г · У {food['c']}г\n\n"
                f"Выбери приём пищи:",
                parse_mode="Markdown",
                reply_markup=meal_keyboard()
            )

    elif data.startswith("meal_"):
        meal_id = data[5:]
        ctx.user_data["selected_meal"] = meal_id
        ctx.user_data["state"] = "waiting_grams"
        food = ctx.user_data.get("picked_food", {})
        # Найдём индекс в results
        results = ctx.user_data.get("search_results", [])
        idx = next((i for i, f in enumerate(results) if f == food), 0)
        await query.edit_message_text(
            f"*{food.get('name','')}* — {food.get('cal',0)} ккал/100г\n\n"
            f"Сколько граммов?",
            parse_mode="Markdown",
            reply_markup=grams_keyboard(idx)
        )

    elif data.startswith("grams_"):
        _, idx_str, grams_str = data.split("_", 2)
        grams = int(grams_str)
        food = ctx.user_data.get("picked_food", {})
        meal_id = ctx.user_data.get("selected_meal", "snack")
        _add_entry(uid, food, meal_id, grams)
        ec = round(food["cal"] * grams / 100)
        await query.edit_message_text(
            f"✅ Добавлено в *{meal_name(meal_id)}*:\n"
            f"*{food['name']}* {grams}г → {ec} ккал",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ Добавить ещё", callback_data="add_food")],
                [InlineKeyboardButton("📊 Сводка", callback_data="summary")],
                [InlineKeyboardButton("🏠 Меню", callback_data="menu")],
            ])
        )

    elif data.startswith("custom_"):
        ctx.user_data["state"] = "waiting_custom_grams"
        food = ctx.user_data.get("picked_food", {})
        await query.edit_message_text(
            f"*{food.get('name','')}*\n\nВведи количество граммов:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data="cancel")]])
        )

    elif data == "clear_day":
        get_user(uid)["log"][today()] = []
        await query.edit_message_text(
            "🗑 Дневник за сегодня очищен.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Меню", callback_data="menu")]])
        )

    elif data == "set_goal":
        ctx.user_data["state"] = "waiting_goal"
        await query.edit_message_text(
            f"🎯 Текущая цель: *{get_user(uid)['goal']} ккал*\n\n"
            f"Введи новую цель (от 500 до 10000):",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data="cancel")]])
        )

    elif data == "cancel":
        ctx.user_data.clear()
        await query.edit_message_text("Выбери действие:", reply_markup=main_keyboard(uid))

async def text_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = update.message.text.strip()
    state = ctx.user_data.get("state")

    if state == "waiting_food":
        ctx.user_data.pop("state", None)
        await update.message.reply_text("🔍 Ищу продукт...")

        # Сначала ищем локально
        results = search_local(text)

        # Если мало результатов — ищем в OpenFoodFacts
        if len(results) < 3:
            off_results = await search_openfoodfacts(text)
            # Объединяем без дублей
            existing = {r["name"].lower() for r in results}
            for r in off_results:
                if r["name"].lower() not in existing:
                    results.append(r)

        if not results:
            await update.message.reply_text(
                f"❌ По запросу «{text}» ничего не найдено.\n\nПопробуй другое название:",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔍 Искать снова", callback_data="add_food")],
                    [InlineKeyboardButton("🏠 Меню", callback_data="menu")],
                ])
            )
            return

        ctx.user_data["search_results"] = results
        text_lines = [f"Найдено {len(results)} продукт(а). Выбери:"]
        await update.message.reply_text(
            "\n".join(text_lines),
            reply_markup=results_keyboard(results)
        )

    elif state == "waiting_custom_grams":
        ctx.user_data.pop("state", None)
        food = ctx.user_data.get("picked_food", {})
        meal_id = ctx.user_data.get("selected_meal", "snack")
        try:
            grams = int(text)
            if grams <= 0: raise ValueError
            _add_entry(uid, food, meal_id, grams)
            ec = round(food["cal"] * grams / 100)
            await update.message.reply_text(
                f"✅ Добавлено: *{food['name']}* {grams}г → {ec} ккал",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("➕ Добавить ещё", callback_data="add_food")],
                    [InlineKeyboardButton("📊 Сводка", callback_data="summary")],
                    [InlineKeyboardButton("🏠 Меню", callback_data="menu")],
                ])
            )
        except ValueError:
            await update.message.reply_text("⚠️ Введи целое число (например: 150)")

    elif state == "waiting_goal":
        ctx.user_data.pop("state", None)
        try:
            goal = int(text)
            if not (500 <= goal <= 10000): raise ValueError
            get_user(uid)["goal"] = goal
            await update.message.reply_text(
                f"✅ Цель: *{goal} ккал/день*",
                parse_mode="Markdown",
                reply_markup=main_keyboard(uid)
            )
        except ValueError:
            await update.message.reply_text("⚠️ Введи число от 500 до 10000")
    else:
        await update.message.reply_text("Используй меню 👇", reply_markup=main_keyboard(uid))

def meal_name(meal_id: str) -> str:
    names = {"breakfast": "Завтрак", "lunch": "Обед", "dinner": "Ужин", "snack": "Перекус"}
    return names.get(meal_id, meal_id)

def _add_entry(uid: int, food: dict, meal_id: str, grams: int):
    get_user(uid)["log"].setdefault(today(), [])
    get_user(uid)["log"][today()].append({
        "name":        food["name"],
        "meal":        meal_id,
        "grams":       grams,
        "cal_per100":  food["cal"],
        "p_per100":    food["p"],
        "f_per100":    food["f"],
        "c_per100":    food["c"],
    })

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    logger.info("Бот запущен с OpenFoodFacts!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
