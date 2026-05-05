from flask import Flask
from flask_socketio import SocketIO
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__, 
    template_folder=os.path.join(BASE_DIR, "templates"),
    static_folder=os.path.join(BASE_DIR, "static")
)
app.secret_key = "secret_key"
socketio = SocketIO(app, cors_allowed_origins="*")