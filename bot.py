import os
import json
import logging

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)
from telegram.ext import (
    Updater,
    CommandHandler,
    CallbackQueryHandler,
    CallbackContext,
    ConversationHandler,
    MessageHandler,
    Filters
)
from google_sheets import write_to_google_sheet

# === Налаштування ===

TOKEN = '7688879325:AAH_Nl7u08zZj3cTDmjHTBSkxWIEMg3XBIc'
GREETING_FILE = 'hello.txt'
VACANCIES_FILE = 'vacancies.txt'
DESCRIPTIONS_FILE = 'vacancy_descriptions.txt'
GROUPS_FILE = 'vacancy_groups.txt'

ASK_NAME, ASK_PHONE, ASK_AGE = range(3)

# === Логування ===

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# === Шлях до відео ===
VIDEO_PATH = "intro.mp4"

# === Завантаження даних ===

def load_greeting():
    with open(GREETING_FILE, 'r', encoding='utf-8') as file:
        return file.read()

def load_vacancies():
    with open(VACANCIES_FILE, 'r', encoding='utf-8') as file:
        return json.load(file)

def load_descriptions():
    with open(DESCRIPTIONS_FILE, 'r', encoding='utf-8') as file:
        blocks = file.read().split('\n\n')
        return {block.split(':\n')[0].strip(): block.split(':\n')[1].strip() for block in blocks if ':\n' in block}

def load_groups():
    with open(GROUPS_FILE, 'r', encoding='utf-8') as file:
        lines = file.readlines()
    groups = {
        'Вакансії для чоловіків': [],
        'Вакансії для жінок': [],
        'Вакансії для сімейних пар': []
    }
    for line in lines:
        if '-' in line:
            title, group = line.strip().split(' - ')
            if group in groups:
                groups[group].append(title.strip())
    return groups

# === Анкета ===

def submit_form(update: Update, context: CallbackContext) -> int:
    user_data = context.user_data
    print("➡️ Початок submit_form")

    try:
        name = user_data.get("name")
        phone = user_data.get("phone")
        age = user_data.get("age")
        vacancy = user_data.get("vacancy")
        source = user_data.get("source", "Telegram")

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        print("📄 Дані для таблиці готові")

        worksheet.append_row([timestamp, name, phone, age, vacancy, source])
        print("✅ Дані записані у таблицю")

        context.bot.send_message(
            chat_id="@robota_cz_24_7",
            text=f"🆕 Нова анкета:\n\n👤 Ім'я: {name}\n📞 Телефон: {phone}\n🎂 Вік: {age}\n💼 Вакансія: {vacancy}"
        )
        print("📢 Повідомлення надіслано в чат координаторів")

        update.message.reply_text("✅ Дякуємо! Ваші дані успішно отримані. Ми зв’яжемось з вами найближчим часом.")
        print("📬 Повідомлення 'Дякуємо' відправлено")

    except Exception as e:
        print("❌ ПОМИЛКА у submit_form:", e)

    return ConversationHandler.END

def cancel_form(update: Update, context: CallbackContext):
    update.message.reply_text("❌ Анкету скасовано.")
    return ConversationHandler.END

# === Обробка команд ===

def start(update: Update, context: CallbackContext):
    greeting = load_greeting()
    keyboard = [[InlineKeyboardButton("▶️ Далі", callback_data='next')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text(greeting)
    try:
        with open(VIDEO_PATH, 'rb') as video:
            update.message.reply_video(video)
    except Exception as e:
        logger.error(f"Помилка при надсиланні відео: {e}")
    update.message.reply_text("Натисніть кнопку нижче, щоб продовжити:", reply_markup=reply_markup)

def handle_next(query, context: CallbackContext):
    keyboard = [
        [InlineKeyboardButton("💁🏻‍♂️Вакансії для чоловіків", callback_data='group_Вакансії для чоловіків')],
        [InlineKeyboardButton("💁🏼‍♀️Вакансії для жінок", callback_data='group_Вакансії для жінок')],
        [InlineKeyboardButton("👩🏼‍❤️‍👨🏻Вакансії для сімейних пар", callback_data='group_Вакансії для сімейних пар')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    query.edit_message_text("Оберіть категорію вакансій:", reply_markup=reply_markup)

def show_vacancies_by_group(query, group_name):
    groups = load_groups()
    group_vacancies = groups.get(group_name, [])
    keyboard = [
        [InlineKeyboardButton(title, callback_data=f'vacancy_{title}')]
        for title in group_vacancies
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    query.edit_message_text(text="Оберіть вакансію:", reply_markup=reply_markup)

def show_vacancy_description(query, data):
    title = data.replace('vacancy_', '')
    descriptions = load_descriptions()
    description = descriptions.get(title, "Опис вакансії недоступний.")
    query.edit_message_text(text=f"{title}\n\n{description}")
    reply_markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Заповнити анкету", callback_data=f"form|{title}")]
    ])
    query.message.reply_text("Бажаєш податись на цю вакансію?", reply_markup=reply_markup)

def button(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    data = query.data
    if data == 'next':
        handle_next(query, context)
    elif data.startswith('group_'):
        group = data.replace('group_', '')
        show_vacancies_by_group(query, group)
    elif data.startswith('vacancy_'):
        show_vacancy_description(query, data)

def start_form(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    context.user_data['vacancy'] = query.data.split('|')[1]
    query.message.reply_text("Введіть ваше ім'я:")
    return ASK_NAME

def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler('start', start))
    dp.add_handler(CallbackQueryHandler(button, pattern='^(next|group_.*|vacancy_.*)$'))

    form_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_form, pattern=r'^form\|')],
        states={
            ASK_NAME: [MessageHandler(Filters.text & ~Filters.command, ask_phone)],
            ASK_PHONE: [MessageHandler(Filters.text & ~Filters.command, ask_age)],
            ASK_AGE: [MessageHandler(Filters.text & ~Filters.command, finish_form)],
        },
        fallbacks=[CommandHandler('cancel', cancel_form)]
    )
    dp.add_handler(form_handler)

    # === Webhook запуск всередині main() ===
    PORT = int(os.environ.get("PORT", "8443"))
    WEBHOOK_URL = os.environ.get("WEBHOOK_URL")

    updater.start_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=TOKEN,
        webhook_url=f"{WEBHOOK_URL}/{TOKEN}"
    )

    updater.idle()

if __name__ == '__main__':
    main()