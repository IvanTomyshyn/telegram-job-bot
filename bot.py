import json
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, CallbackContext, ConversationHandler, MessageHandler, Filters
from google_sheets import write_to_google_sheet
from datetime import datetime

# Увімкнення логування
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# === СТАНИ ДЛЯ АНКЕТИ ===
NAME, PHONE, AGE, SOURCE = range(4)

# === /start ===
def start(update: Update, context: CallbackContext) -> None:
    with open("hello.txt", "r", encoding="utf-8") as f:
        greeting = f.read()
    update.message.reply_text(greeting)

    with open("intro.mp4", "rb") as video:
        context.bot.send_video(chat_id=update.effective_chat.id, video=video)

    keyboard = [[InlineKeyboardButton("➡️ Далі", callback_data="next")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    context.bot.send_message(chat_id=update.effective_chat.id, text="Натисни кнопку, щоб переглянути вакансії:", reply_markup=reply_markup)

# === Обробка "Далі" ===
def next_step(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    query.answer()
    keyboard = [
        [InlineKeyboardButton("👨‍🔧 Вакансії для чоловіків", callback_data="чоловіки")],
        [InlineKeyboardButton("👩🏼‍💼 Вакансії для жінок", callback_data="жінки")],
        [InlineKeyboardButton("👩‍❤️‍👨 Вакансії для сімейних пар", callback_data="пари")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    query.edit_message_text(text="Оберіть категорію вакансій:", reply_markup=reply_markup)

# === Обробка вибору групи вакансій ===
def handle_group_selection(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    group = query.data
    query.answer()

    with open("vacancy_groups.txt", "r", encoding="utf-8") as f:
        groups = f.read().splitlines()

    group_dict = {}
    current_group = None
    for line in groups:
        if line.startswith("#"):
            current_group = line.replace("#", "").strip()
            group_dict[current_group] = []
        elif current_group:
            group_dict[current_group].append(line.strip())

    vacancies = group_dict.get(group, [])

    if not vacancies:
        query.edit_message_text("На жаль, вакансій у цій категорії наразі немає.")
        return

    buttons = [[InlineKeyboardButton(vacancy, callback_data=vacancy)] for vacancy in vacancies]
    reply_markup = InlineKeyboardMarkup(buttons)
    query.edit_message_text("Оберіть вакансію:", reply_markup=reply_markup)

# === Обробка вибору вакансії ===
def show_vacancy_description(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    selected_vacancy = query.data
    query.answer()

    with open("vacancy_descriptions.txt", "r", encoding="utf-8") as f:
        descriptions = f.read().split("\n\n")

    description_dict = {}
    for block in descriptions:
        lines = block.strip().split("\n")
        if lines:
            title = lines[0].strip()
            description = "\n".join(lines[1:]).strip()
            description_dict[title] = description

    full_description = description_dict.get(selected_vacancy, "Опис вакансії тимчасово недоступний.")
    buttons = [[InlineKeyboardButton("✍️ Заповнити анкету", callback_data=f"form|{selected_vacancy}")]]
    reply_markup = InlineKeyboardMarkup(buttons)
    query.edit_message_text(text=full_description, reply_markup=reply_markup)

# === Обробка кнопки "Заповнити анкету" ===
def start_form(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    query.answer()
    vacancy = query.data.split("|", 1)[1]
    context.user_data['vacancy'] = vacancy
    query.edit_message_text("Введіть, будь ласка, ваше ім’я:")
    return NAME

def get_name(update: Update, context: CallbackContext) -> int:
    context.user_data['name'] = update.message.text
    update.message.reply_text("Ваш номер телефону:")
    return PHONE

def get_phone(update: Update, context: CallbackContext) -> int:
    context.user_data['phone'] = update.message.text
    update.message.reply_text("Скільки вам років?")
    return AGE

def get_age(update: Update, context: CallbackContext) -> int:
    context.user_data['age'] = update.message.text
    update.message.reply_text("Звідки ви дізнались про нас?")
    return SOURCE

def get_source(update: Update, context: CallbackContext) -> int:
    context.user_data['source'] = update.message.text

    row = [
        datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        context.user_data['name'],
        context.user_data['phone'],
        context.user_data['age'],
        context.user_data['vacancy'],
        context.user_data['source']
    ]

    write_to_google_sheet(row)

    update.message.reply_text("Дякуємо! Вашу анкету надіслано координатору. Очікуйте на зворотній зв'язок.")
    return ConversationHandler.END

def cancel(update: Update, context: CallbackContext) -> int:
    update.message.reply_text('Анкету скасовано.')
    return ConversationHandler.END

# === Основна функція запуску ===
def main() -> None:
    TOKEN = "7688879325:AAH_Nl7u08zZj3cTDmjHTBSkxWIEMg3XBIc"
    updater = Updater(TOKEN, use_context=True)
    dispatcher = updater.dispatcher

    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CallbackQueryHandler(next_step, pattern='^next$'))
    dispatcher.add_handler(CallbackQueryHandler(handle_group_selection, pattern='^(чоловіки|жінки|пари)$'))
    dispatcher.add_handler(CallbackQueryHandler(show_vacancy_description, pattern='^(?!next$|чоловіки$|жінки$|пари$|form\|).+'))
    dispatcher.add_handler(CallbackQueryHandler(start_form, pattern='^form\|'))

    form_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_form, pattern='^form\|')],
        states={
            NAME: [MessageHandler(Filters.text & ~Filters.command, get_name)],
            PHONE: [MessageHandler(Filters.text & ~Filters.command, get_phone)],
            AGE: [MessageHandler(Filters.text & ~Filters.command, get_age)],
            SOURCE: [MessageHandler(Filters.text & ~Filters.command, get_source)]
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )

    dispatcher.add_handler(form_handler)
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
