from flask import Flask
app = Flask(name)

@app.route('/')
def hello():
    return "Telegram Job Bot - simple test"

if name == "main":
    app.run()