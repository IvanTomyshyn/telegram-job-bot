from flask import Flask
app = Flask(__name__)

@app.route('/')
def hello():
    return "Telegram Job Bot - simple test"

if __name__ == "__main__":
    app.run()