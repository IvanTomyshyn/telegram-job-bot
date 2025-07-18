# google_sheets.py

import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# Підключення до Google Таблиці
def connect_to_sheet():
    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = Credentials.from_service_account_file("credentials.json", scopes=scope)
    client = gspread.authorize(creds)
    sheet = client.open("Telegram_Bot_Anketa").sheet1
    return sheet

# Запис анкети
def write_to_google_sheet(name, phone, age, vacancy, source="Telegram Bot"):
    sheet = connect_to_sheet()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sheet.append_row([timestamp, name, phone, age, vacancy, source])