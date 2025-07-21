import os
import json
import logging
from datetime import datetime
from flask import Flask, request

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Bot
from telegram.ext import (
    Dispatcher,
    CommandHandler,
    CallbackQueryHandler,
    CallbackContext,
    ConversationHandler,
    MessageHandler,
    Filters
)
from google_sheets import write_to_google_sheet

# === Flask ===
app = Flask(__name__)
TOKEN = os.environ.get("TOKEN")
bot = Bot(token=TOKEN)

# === Dispatcher ===
dispatcher = Dispatcher(bot=bot, update_queue=None, workers=4, use_context=True)

# === Логування ===
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# === Змінні ===
GREETING_FILE = 'hello.txt'
DESCRIPTIONS_FILE = 'vacancy_descriptions'
GROUPS_FILE = 'vacancy_groups'
VIDEO_PATH = 'intro.mp4'
ASK_NAME, ASK_PHONE, ASK_AGE = range(3)

# === Завантаження даних ===
def load_greeting():
    with open(GREETING_FILE, 'r', encoding='utf-8') as file:
        return file.read()

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
    try:
        name = user_data.get("name")
        phone = user_data.get("phone")
        age = user_data.get("age")
        vacancy = user_data.get("vacancy")
        source = user_data.get("source", "Telegram")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        write_to_google_sheet([timestamp, name, phone, age, vacancy, source])

        context.bot.send_message(
            chat_id="@robota_cz_24_7",
            text=f"🆕 Нова анкета:\n\n👤 Ім'я: {name}\n📞 Телефон: {phone}\n🎂 Вік: {age}\n💼 Вакансія: {vacancy}"
        )
        update.message.reply_text("✅ Дякуємо! Ваші дані успішно отримані.")
    except Exception as e:
        logger.error(f"❌ ПОМИЛКА у submit_form: {e}")
    return ConversationHandler.END

def cancel_form(update: Update, context: CallbackContext):
    update.message.reply_text("❌ Анкету скасовано.")
    return ConversationHandler.END

# === Команди ===
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
    query.edit_message_text("Оберіть категорію вакансій:", reply_markup=InlineKeyboardMarkup(keyboard))

def show_vacancies_by_group(query, group_name):
    groups = load_groups()
    group_vacancies = groups.get(group_name, [])
    keyboard = [[InlineKeyboardButton(title, callback_data=f'vacancy_{title}')] for title in group_vacancies]
    query.edit_message_text(text="Оберіть вакансію:", reply_markup=InlineKeyboardMarkup(keyboard))

def show_vacancy_description(query, data):
    title = data.replace('vacancy_', '')
    descriptions = load_descriptions()
    description = descriptions.get(title, "Опис вакансії недоступний.")
    query.edit_message_text(text=f"{title}\n\n{description}")
    query.message.reply_text("Бажаєш податись на цю вакансію?", reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Заповнити анкету", callback_data=f"form|{title}")]
    ]))

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

def ask_phone(update: Update, context: CallbackContext) -> int:
    context.user_data["name"] = update.message.text
    update.message.reply_text("Введіть ваш номер телефону:")
    return ASK_PHONE

def ask_age(update: Update, context: CallbackContext) -> int:
    context.user_data["phone"] = update.message.text
    update.message.reply_text("Скільки вам років?")
    return ASK_AGE

def finish_form(update: Update, context: CallbackContext) -> int:
    context.user_data["age"] = update.message.text
    return submit_form(update, context)

def start_form(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    context.user_data['vacancy'] = query.data.split('|')[1]
    query.message.reply_text("Введіть ваше ім'я:")
    return ASK_NAME

# === Роутинг Flask (Webhook) ===
@app.route(f'/{TOKEN}', methods=['POST'])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    dispatcher.process_update(update)
    return 'ok'

@app.route('/')
def index():
    return "🤖 Бот запущено на Render і працює!"

# === Обробники ===
dispatcher.add_handler(CommandHandler('start', start))
dispatcher.add_handler(CallbackQueryHandler(button, pattern='^(next|group_.*|vacancy_.*)$'))
dispatcher.add_handler(CallbackQueryHandler(start_form, pattern=r'^form\|'))

form_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(start_form, pattern=r'^form\|')],
    states={
        ASK_NAME: [MessageHandler(Filters.text & ~Filters.command, ask_phone)],
        ASK_PHONE: [MessageHandler(Filters.text & ~Filters.command, ask_age)],
        ASK_AGE: [MessageHandler(Filters.text & ~Filters.command, finish_form)],
    },
    fallbacks=[CommandHandler('cancel', cancel_form)]
)
dispatcher.add_handler(form_handler)
