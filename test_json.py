import json

with open("credentials.json", "r", encoding="utf-8") as f:
    data = json.load(f)

print(data["client_email"])