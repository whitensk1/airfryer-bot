import os
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from recipe_core import get_next_recipe, get_image_url, mark_posted, stats

load_dotenv()

TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
TG_CHAT_ID = os.getenv("TG_CHAT_ID")  # канал: -100... или @username
ADMIN_USER_IDS = set(
    int(x.strip()) for x in (os.getenv("ADMIN_USER_IDS", "")).split(",") if x.strip().isdigit()
)

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_USER_IDS

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user:
        return
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("Доступ запрещён.")
        return
    await update.message.reply_text(
        "Команды:\n"
        "/next — опубликовать следующий рецепт\n"
        "/stats — статистика\n"
    )

async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or not is_admin(update.effective_user.id):
        await update.message.reply_text("Доступ запрещён.")
        return

    s = stats()
    await update.message.reply_text(
        "Статистика:\n"
        f"• Всего рецептов: {s['total']}\n"
        f"• Ready: {s['ready']}\n"
        f"• Уже публиковались: {s['posted']}\n"
        f"• Ready осталось (включая уже публиковавшиеся): {s['remaining_ready']}\n"
    )

async def cmd_next(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or not is_admin(update.effective_user.id):
        await update.message.reply_text("Доступ запрещён.")
        return

    recipe = get_next_recipe()
    if not recipe:
        await update.message.reply_text("Нет рецептов со статусом ready.")
        return

    title = recipe["title"].strip()
    body = recipe["body"].strip()
    caption = f"<b>{title}</b>\n\n{body}"

    photo_url = get_image_url(recipe)
    if not photo_url:
        await update.message.reply_text("У рецепта нет image_path/image_url — нечего постить.")
        return

    # Публикация в канал (через bytes, без URL)
    import requests
    from io import BytesIO

    img = requests.get(photo_url, timeout=30)
    img.raise_for_status()

    await context.bot.send_photo(
        chat_id=TG_CHAT_ID,
        photo=BytesIO(img.content),
        caption=caption[:1024],
        parse_mode="HTML",
    )

    # Отметить в базе как опубликованный сегодня
    mark_posted(recipe["id"])

    await update.message.reply_text(f"Опубликовано: {title}")

def main():
    assert TG_BOT_TOKEN and TG_CHAT_ID, "TG_BOT_TOKEN/TG_CHAT_ID missing"
    assert ADMIN_USER_IDS, "ADMIN_USER_IDS missing"

    app = Application.builder().token(TG_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("next", cmd_next))
    app.add_handler(CommandHandler("stats", cmd_stats))

    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()