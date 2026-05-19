from gevent import monkey
monkey.patch_all()

from flask import  session, render_template, redirect, url_for
from core import app, socketio
from functools import wraps
from pooheads.pooheads import pooheads_bp
from sevens.sevens import sevens_bp
from auth.auth import auth_bp, get_chips, load_users, get_achievements, get_recent_players,  get_join_code
from blackjack.blackjack import blackjack_bp
from flask_socketio import SocketIO, emit
from slots.slots import slots_bp
from poker.poker import poker_bp 


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

@socketio.on('send_global_msg')
def handle_global(data):
    if session.get("username"):
        emit('receive_msg', {
            'sender': session.get("username"),
            'msg': data['msg'],
            'type': 'global'
        }, broadcast=True)

@socketio.on('send_private_msg')
def handle_private(data):
    if session.get("username"):
        sender = session.get("username")
        recipient = data['to']
        msg_content = data['msg']
        payload = {
            'sender': sender,
            'msg': msg_content,
            'type': 'private',
            'target': recipient
        }
        emit('receive_msg', payload, room=recipient)
        if sender != recipient:
            emit('receive_msg', payload, room=sender)

@app.route("/")
@login_required
def home():
    username = session["username"]
    data = load_users()
    user = data["users"].get(username, {})
    stats = user.get("stats", {})

    history = list(reversed(user.get("history", [])))[:5]

    chips = get_chips(username)

    leaderboard = sorted(
        [{"username": u, "chips": d["chips"]} for u, d in data["users"].items()],
        key=lambda x: x["chips"], reverse=True
    )[:5]


    achievements   = get_achievements(username)
    recent_players = get_recent_players(username)

    return render_template("index.html",
        username=username,
        chips=chips,
        leaderboard=leaderboard,
        join_code=get_join_code(),
        stats=stats,
        history=history,
        achievements=achievements,
        recent_players=recent_players
    )


@app.route("/school")
@login_required
def school():

    return render_template("school.html",
        username=session["username"],
        join_code=get_join_code()
    )
@app.route("/school2")
@login_required
def school2():
    username = session["username"]
    data = load_users()
    user = data["users"].get(username, {})
    stats = user.get("stats", {})

    history = list(reversed(user.get("history", [])))[:5]

    chips = get_chips(username)

    leaderboard = sorted(
        [{"username": u, "chips": d["chips"]} for u, d in data["users"].items()],
        key=lambda x: x["chips"], reverse=True
    )[:5]


    achievements   = get_achievements(username)
    recent_players = get_recent_players(username)

    return render_template("school2.html",
        username=username,
        chips=chips,
        leaderboard=leaderboard,
        join_code=get_join_code(),
        stats=stats,
        history=history,
        achievements=achievements,
        recent_players=recent_players
    )
if __name__ == "__main__":
    socketio.run(app, debug=True)
