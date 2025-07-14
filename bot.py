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
VIDEO_PATH = r"C:\\Users\\admin\\Desktop\\TelegramBot\\intro.mp4"

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

def start_form(update: Update, context: CallbackContext):
    query = update.callback_query
    _, vacancy = query.data.split('|')
    context.user_data['vacancy'] = vacancy
    query.answer()
    query.message.reply_text("👤 Введи своє *ім’я та прізвище*:", parse_mode='Markdown')
    return ASK_NAME

def ask_phone(update: Update, context: CallbackContext):
    context.user_data['name'] = update.message.text
    update.message.reply_text("📞 Введи свій *номер телефону*:", parse_mode='Markdown')
    return ASK_PHONE

def ask_age(update: Update, context: CallbackContext):
    context.user_data['phone'] = update.message.text
    update.message.reply_text("🎂 Скільки тобі *повних років*:", parse_mode='Markdown')
    return ASK_AGE

def finish_form(update: Update, context: CallbackContext):
    context.user_data['age'] = update.message.text

    name = context.user_data['name']
    phone = context.user_data['phone']
    age = context.user_data['age']
    vacancy = context.user_data['vacancy']

    write_to_google_sheet(name, phone, age, vacancy)

    update.message.reply_text("✅ *Дякуємо!* Ми отримали твої дані.\nНайближчим часом координатор зв’яжеться з тобою.", parse_mode='Markdown')

    context.bot.send_message(
        chat_id='@robota_cz_24_7',
        text=f"📥 *Нова анкета!*\n👤 {name}\n📞 {phone}\n🎂 {age} років\n💼 {vacancy}",
        parse_mode='Markdown'
    )

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

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
