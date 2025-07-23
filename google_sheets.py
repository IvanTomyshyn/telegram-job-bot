import os
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Читання JSON із змінної середовища
credentials_raw = os.environ.get('GOOGLE_CREDENTIALS')

# Перевірка, якщо не знайдено
if not credentials_raw:
    raise Exception("GOOGLE_CREDENTIALS env variable not found!")

# Декодування JSON
try:
    credentials_info = json.loads(credentials_raw)
except json.JSONDecodeError:
    raise Exception("GOOGLE_CREDENTIALS is not valid JSON!")

# Авторизація Google Sheets
scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
credentials = ServiceAccountCredentials.from_json_keyfile_dict(credentials_info, scope)
client = gspread.authorize(credentials)

# Підключення до таблиці
sheet = client.open(os.environ['GOOGLE_SHEET_NAME']).sheet1

# Функція запису в таблицю
def write_to_google_sheet(data: list):
    sheet.append_row(data)