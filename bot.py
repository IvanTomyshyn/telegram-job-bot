import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import (
    Updater,
    CommandHandler,
    CallbackQueryHandler,
    CallbackContext,
    ConversationHandler,
    MessageHandler,
    Filters,
)
from google_sheets import write_to_google_sheet
from datetime import datetime

# === Logging ===
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# === Conversation states ===
(SELECTING_CATEGORY, SELECTING_VACANCY, ASK_NAME, ASK_PHONE, ASK_AGE, CONFIRM_DATA) = range(6)

# === Load content ===
def load_greeting():
    with open("hello.txt", "r", encoding="utf-8") as f:
        return f.read()

def load_vacancy_descriptions():
    with open("vacancy_descriptions", "r", encoding="utf-8") as f:
        content = f.read()
    blocks = content.strip().split("\n\n")
    descriptions = {}
    for block in blocks:
        if " - " in block:
            title, desc = block.split(" - ", 1)
            descriptions[title.strip()] = desc.strip()
    return descriptions

def load_vacancy_groups():
    with open("vacancy_groups", "r", encoding="utf-8") as f:
        content = f.read()
    lines = content.strip().split("\n")
    groups = {"men": [], "women": [], "couples": []}
    for line in lines:
        if " - " in line:
            group, vacancy = line.split(" - ", 1)
            key = group.lower().strip()
            if key in groups:
                groups[key].append(vacancy.strip())
    return groups

def load_vacancies():
    import json
    with open("vacancies.json", "r", encoding="utf-8") as f:
        return json.load(f)

# === Handlers ===
def start(update: Update, context: CallbackContext) -> int:
    greeting = load_greeting()
    update.message.reply_text(greeting)
    with open("intro.mp4", "rb") as video:
        update.message.reply_video(video)
    keyboard = [[InlineKeyboardButton("Далі ▶️", callback_data="next")]]
    update.message.reply_text("Готові дізнатись більше?", reply_markup=InlineKeyboardMarkup(keyboard))
    return SELECTING_CATEGORY

def handle_next(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    query.answer()
    keyboard = [
        [InlineKeyboardButton("Вакансії для чоловіків", callback_data="men")],
        [InlineKeyboardButton("Вакансії для жінок", callback_data="women")],
        [InlineKeyboardButton("Вакансії для сімейних пар", callback_data="couples")],
    ]
    query.edit_message_text("Оберіть категорію вакансій:", reply_markup=InlineKeyboardMarkup(keyboard))
    return SELECTING_VACANCY

def handle_group_selection(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    query.answer()
    group = query.data
    context.user_data["group"] = group
    groups = load_vacancy_groups()
    vacancies = groups.get(group, [])
    keyboard = [[InlineKeyboardButton(v, callback_data=v)] for v in vacancies]
    query.edit_message_text("Оберіть вакансію:", reply_markup=InlineKeyboardMarkup(keyboard))
    return SELECTING_VACANCY

def handle_vacancy_selection(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    query.answer()
    vacancy = query.data
    context.user_data["vacancy"] = vacancy
    descriptions = load_vacancy_descriptions()
    description = descriptions.get(vacancy, "Опис вакансії наразі недоступний.")
    text = f"*{vacancy}*\n\n{description}\n\nНатисніть \"Заповнити анкету\", щоб подати заявку."
    keyboard = [[InlineKeyboardButton("Заповнити анкету 📝", callback_data="fill_form")]]
    query.edit_message_text(text=text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    return ASK_NAME

def fill_form(update: Update, context: CallbackContext) -> int:
    update.callback_query.answer()
    update.callback_query.edit_message_text("Введіть ваше *ім’я та прізвище*:", parse_mode="Markdown")
    return ASK_NAME

def ask_phone(update: Update, context: CallbackContext) -> int:
    context.user_data["name"] = update.message.text
    update.message.reply_text("Введіть ваш *номер телефону* (+420 або +380):", parse_mode="Markdown")
    return ASK_PHONE

def ask_age(update: Update, context: CallbackContext) -> int:
    context.user_data["phone"] = update.message.text
    update.message.reply_text("Скільки вам повних років?")
    return ASK_AGE

def confirm_data(update: Update, context: CallbackContext) -> int:
    context.user_data["age"] = update.message.text
    data = context.user_data
    summary = (
        f"📄 Дані анкети:\n\n"
        f"👤 Ім’я: {data['name']}\n"
        f"📞 Телефон: {data['phone']}\n"
        f"🎂 Вік: {data['age']}\n"
        f"💼 Вакансія: {data['vacancy']}"
    )
    update.message.reply_text("Дякуємо! Ваші дані збережено. Наш менеджер з вами зв'яжеться.")
    write_to_google_sheet({
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "name": data["name"],
        "phone": data["phone"],
        "age": data["age"],
        "vacancy": data["vacancy"],
        "source": "Telegram"
    })
    context.bot.send_message(
        chat_id='@robota_cz_24_7',
        text=f"🔔 Нова заявка!\n\n{summary}"
    )
    return ConversationHandler.END

def cancel(update: Update, context: CallbackContext) -> int:
    update.message.reply_text("Дію скасовано.")
    return ConversationHandler.END

# === Main ===
def main():
    TOKEN = os.getenv("TOKEN")
    if not TOKEN:
        raise ValueError("TOKEN is missing from environment variables.")
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            SELECTING_CATEGORY: [CallbackQueryHandler(handle_next, pattern="^next$")],
            SELECTING_VACANCY: [
                CallbackQueryHandler(handle_group_selection, pattern="^(men|women|couples)$"),
                CallbackQueryHandler(handle_vacancy_selection)
            ],
            ASK_NAME: [CallbackQueryHandler(fill_form, pattern="^fill_form$"), MessageHandler(Filters.text & ~Filters.command, ask_phone)],
            ASK_PHONE: [MessageHandler(Filters.text & ~Filters.command, ask_age)],
            ASK_AGE: [MessageHandler(Filters.text & ~Filters.command, confirm_data)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

import os
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, MessageHandler, Filters

# === 1. Отримуємо токен і URL вебхука ===
TOKEN = os.environ.get("TOKEN")
WEBHOOK_URL = f"https://{os.environ['RAILWAY_STATIC_URL']}"

# === 2. Ініціалізуємо бота ===
updater = Updater(TOKEN, use_context=True)
dispatcher = updater.dispatcher

# === 3. Додаємо обробники ===
dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(CallbackQueryHandler(handle_next, pattern="^group_"))
dispatcher.add_handler(CallbackQueryHandler(handle_group_selection, pattern="^vacancy_"))
dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_form)) # якщо анкета

# === 4. Запускаємо webhook (для Railway) ===
PORT = int(os.environ.get("PORT", 8443))

updater.start_webhook(
    listen="0.0.0.0",
    port=PORT,
    url_path=TOKEN,
    webhook_url=f"{WEBHOOK_URL}/{TOKEN}"
)

updater.idle()

if __name__ == "__main__":
    main()
# redeploy to refresh env vars