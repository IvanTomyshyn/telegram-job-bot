import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, CallbackContext, ConversationHandler, MessageHandler, Filters
from google_sheets import write_to_google_sheet
from datetime import datetime

# === Logging ===
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# === Стан для ConversationHandler ===
(SELECTING_CATEGORY, SELECTING_VACANCY, ASK_NAME, ASK_PHONE, ASK_AGE, CONFIRM_DATA) = range(6)

# === Завантаження текстів з .txt файлів ===
def load_greeting():
    with open("hello.txt", "r", encoding="utf-8") as f:
        return f.read()

def load_vacancy_descriptions():
    with open("vacancy_descriptions.txt", "r", encoding="utf-8") as f:
        content = f.read()
    blocks = content.strip().split("\n\n")
    descriptions = {}
    for block in blocks:
        if " - " in block:
            title, desc = block.split(" - ", 1)
            descriptions[title.strip()] = desc.strip()
    return descriptions

def load_vacancy_groups():
    with open("vacancy_groups.txt", "r", encoding="utf-8") as f:
        lines = f.readlines()
    groups = {"men": [], "women": [], "couples": []}
    for line in lines:
        if " - " in line:
            title, group = line.strip().split(" - ")
            if group.lower() == "чоловіки":
                groups["men"].append(title.strip())
            elif group.lower() == "жінки":
                groups["women"].append(title.strip())
            elif group.lower() == "пари":
                groups["couples"].append(title.strip())
    return groups

# === Команди ===
def start(update: Update, context: CallbackContext) -> int:
    greeting = load_greeting()
    update.message.reply_text(greeting)
    video_path = 'intro.mp4'
    if os.path.exists(video_path):
        with open(video_path, 'rb') as video:
            update.message.reply_video(video=InputFile(video))
    keyboard = [[InlineKeyboardButton("Далі ▶️", callback_data="next")]]
    update.message.reply_text("Після перегляду просто натисни «Далі» і ми підберемо вакансію, яка підійде саме тобі 😉", reply_markup=InlineKeyboardMarkup(keyboard))
    return SELECTING_CATEGORY

def handle_group_selection(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    query.answer()
    selected = query.data
    context.user_data['group'] = selected

    groups = load_vacancy_groups()
    vacancies = groups.get(selected, [])
    if not vacancies:
        query.edit_message_text("На жаль, вакансій у цій категорії наразі немає.")
        return ConversationHandler.END

    keyboard = [[InlineKeyboardButton(vac, callback_data=vac)] for vac in vacancies]
    query.edit_message_text("Оберіть вакансію:", reply_markup=InlineKeyboardMarkup(keyboard))
    return SELECTING_VACANCY

def handle_vacancy_selection(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    query.answer()
    vacancy = query.data
    context.user_data['vacancy'] = vacancy

    descriptions = load_vacancy_descriptions()
    description = descriptions.get(vacancy, "Опис вакансії наразі недоступний.")
    query.edit_message_text(f"*{vacancy}*\n\n{description}\n\nНатисніть "Заповнити анкету", щоб подати заявку.",
                            parse_mode='Markdown',
                            reply_markup=InlineKeyboardMarkup(
                                [[InlineKeyboardButton("Заповнити анкету 📝", callback_data="fill_form")]]))
    return ASK_NAME

def fill_form(update: Update, context: CallbackContext) -> int:
    update.callback_query.answer()
    update.callback_query.edit_message_text("Введіть ваше *ім'я та прізвище*:", parse_mode='Markdown')
    return ASK_NAME

def ask_phone(update: Update, context: CallbackContext) -> int:
    context.user_data['name'] = update.message.text
    update.message.reply_text("Введіть ваш *номер телефону* (з +420 або +380):", parse_mode='Markdown')
    return ASK_PHONE

def ask_age(update: Update, context: CallbackContext) -> int:
    context.user_data['phone'] = update.message.text
    update.message.reply_text("Скільки вам повних років?")
    return ASK_AGE

def confirm_data(update: Update, context: CallbackContext) -> int:
    context.user_data['age'] = update.message.text
    data = context.user_data
    text = f"🔎 Перевірте дані:\n\n👤 Ім'я: {data['name']}\n📞 Телефон: {data['phone']}\n🎂 Вік: {data['age']}\n💼 Вакансія: {data['vacancy']}\n\nНатисніть 'Підтвердити', щоб надіслати."
    keyboard = [[InlineKeyboardButton("Підтвердити ✅", callback_data="submit")]]
    update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    return CONFIRM_DATA

def submit_form(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    query.answer()
    data = context.user_data
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    write_to_google_sheet([
        timestamp,
        data['name'],
        data['phone'],
        data['age'],
        data['vacancy'],
        'Telegram'
    ])
    query.edit_message_text("✅ Дякуємо! Вашу анкету успішно надіслано. Очікуйте дзвінка найближчим часом.")
    return ConversationHandler.END

def main():
    TOKEN = os.getenv("BOT_TOKEN")
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            SELECTING_CATEGORY: [
                CallbackQueryHandler(handle_group_selection, pattern='^(men|women|couples)$'),
                CallbackQueryHandler(lambda u, c: u.callback_query.message.reply_text("Оберіть категорію:", reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("Вакансії для чоловіків", callback_data="men")],
                    [InlineKeyboardButton("Вакансії для жінок", callback_data="women")],
                    [InlineKeyboardButton("Вакансії для сімейних пар", callback_data="couples")],
                ])), pattern='^next$')
            ],
            SELECTING_VACANCY: [CallbackQueryHandler(handle_vacancy_selection)],
            ASK_NAME: [CallbackQueryHandler(fill_form, pattern='^fill_form$'), MessageHandler(Filters.text & ~Filters.command, ask_phone)],
            ASK_PHONE: [MessageHandler(Filters.text & ~Filters.command, ask_age)],
            ASK_AGE: [MessageHandler(Filters.text & ~Filters.command, confirm_data)],
            CONFIRM_DATA: [CallbackQueryHandler(submit_form, pattern='^submit$')]
        },
        fallbacks=[]
    )

    dp.add_handler(conv_handler)
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()