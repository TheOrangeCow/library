from flask import Flask
from dotenv import load_dotenv
from flask_socketio import SocketIO
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

load_dotenv()

KEY = os.getenv("KEY")

app = Flask(__name__, 
    template_folder=os.path.join(BASE_DIR, "templates"),
    static_folder=os.path.join(BASE_DIR, "static")
)
app.secret_key = KEY
socketio = SocketIO(app, async_mode="gevent", cors_allowed_origins="*")
