from gevent import monkey
monkey.patch_all()

from flask import  session, render_template, redirect, url_for
from core import app, socketio
from functools import wraps
from pooheads.pooheads import pooheads_bp
from sevens.sevens import sevens_bp
from auth.auth import auth_bp, get_chips, load_users, get_achievements, get_recent_players,  get_join_code, get_theme
from blackjack.blackjack import blackjack_bp
from flask_socketio import SocketIO, emit
from slots.slots import slots_bp
from poker.poker import poker_bp
import os
import logging

logger = logging.getLogger(__name__)

app.register_blueprint(poker_bp)
app.register_blueprint(slots_bp)
app.register_blueprint(blackjack_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(pooheads_bp)
app.register_blueprint(sevens_bp)

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "username" not in session:
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return decorated

def validate_message(msg, max_length=500):
    """Validate and sanitize message content."""
    if not isinstance(msg, str):
        return None
    msg = msg.strip()
    if not msg or len(msg) > max_length:
        return None
    return msg

@socketio.on('send_global_msg')
def handle_global(data):
    """Handle global message broadcast with validation."""
    try:
        if not session.get("username"):
            return False
        
        if not isinstance(data, dict) or 'msg' not in data:
            logger.warning(f"Invalid global message data from {session.get('username')}")
            return False
        
        msg = validate_message(data['msg'])
        if not msg:
            return False
        
        emit('receive_msg', {
            'sender': session.get("username"),
            'msg': msg,
            'type': 'global'
        }, broadcast=True)
        return True
    except Exception as e:
        logger.error(f"Error handling global message: {str(e)}")
        return False

@socketio.on('send_private_msg')
def handle_private(data):
    """Handle private message with validation."""
    try:
        if not session.get("username"):
            return False
        
        if not isinstance(data, dict) or 'to' not in data or 'msg' not in data:
            logger.warning(f"Invalid private message data from {session.get('username')}")
            return False
        
        sender = session.get("username")
        recipient = str(data['to']).strip()
        msg = validate_message(data['msg'])
        
        if not msg or not recipient:
            return False
        
        # Validate recipient exists
        users_data = load_users()
        if recipient not in users_data.get("users", {}):
            logger.warning(f"User {sender} attempted to message non-existent user {recipient}")
            return False
        
        payload = {
            'sender': sender,
            'msg': msg,
            'type': 'private',
            'target': recipient
        }
        emit('receive_msg', payload, room=recipient)
        if sender != recipient:
            emit('receive_msg', payload, room=sender)
        return True
    except Exception as e:
        logger.error(f"Error handling private message: {str(e)}")
        return False

def render_game_dashboard(template_name, username):
    """Shared logic for rendering game dashboard pages."""
    try:
        data = load_users()
        user = data["users"].get(username, {})
        stats = user.get("stats", {})
        history = list(reversed(user.get("history", [])))[:5]
        chips = get_chips(username)
        
        leaderboard = sorted(
            [{"username": u, "chips": d["chips"]} for u, d in data["users"].items()],
            key=lambda x: x["chips"], reverse=True
        )[:5]
        
        achievements = get_achievements(username)
        recent_players = get_recent_players(username)
        
        return render_template(template_name,
            username=username,
            chips=chips,
            theme=get_theme(username),
            leaderboard=leaderboard,
            join_code=get_join_code(),
            stats=stats,
            history=history,
            achievements=achievements,
            recent_players=recent_players
        )
    except Exception as e:
        logger.error(f"Error rendering game dashboard: {str(e)}")
        return render_template("error.html", error="Failed to load dashboard"), 500

@app.route("/")
@login_required
def home():
    return render_game_dashboard("index.html", session["username"])

@app.route("/school")
@login_required
def school2():
    return render_game_dashboard("school2.html", session["username"])

if __name__ == "__main__":
    socketio.run(app, debug=True, host="0.0.0.0", port=5000)
