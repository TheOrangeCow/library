from flask import Flask, session, request
from flask_socketio import SocketIO, emit, join_room
from dotenv import load_dotenv
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

active_users = {}
away_users = set()

@socketio.on('tab_hidden')
def handle_tab_hidden():
    if session.get("username"):
        username = session.get("username")
        away_users.add(username)
        emit_status_update()

@socketio.on('tab_visible')
def handle_tab_visible():
    if session.get("username"):
        username = session.get("username")
        away_users.discard(username)
        emit_status_update()

def emit_status_update():
    user_status_list = []
    unique_usernames = list(set(active_users.values()))
    for user in unique_usernames:
        status = "Away" if user in away_users else "Active"
        user_status_list.append({"name": user, "status": status})
    emit('update_user_list', user_status_list, broadcast=True)

@socketio.on('connect')
def handle_connect():
    if session.get("username"):
        username = session.get("username")
        active_users[request.sid] = username
        join_room(username)
        emit_status_update()

@socketio.on('disconnect')
def handle_disconnect():
    if request.sid in active_users:
        user = active_users[request.sid]
        del active_users[request.sid]
        if user not in active_users.values():
            away_users.discard(user)
        emit_status_update()

