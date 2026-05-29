import hashlib, hmac, os, math
from gevent import sleep, spawn
from gevent.lock import RLock
from flask import Blueprint, session, redirect, url_for, render_template, request
from flask_socketio import join_room, leave_room, emit
from functools import wraps

from core import app, socketio
from auth.auth import get_theme, get_chips, update_chips, record_result

crash_bp = Blueprint(
    "crash",
    __name__,
    template_folder="templates",
    static_folder="static",
    static_url_path="/crash/static",
)


rooms = {}
rooms_lock = RLock()

import random

MAX_PLAYERS = 50

def generate_crash_point() -> float:
    seed = os.urandom(16).hex()
    h = hmac.new(b"crash", seed.encode(), hashlib.sha256).hexdigest()
    n = int(h[:8], 16)
    if n % 33 == 0:
        return 1.00
    result = max(1.00, (100 * 2**32) / ((n % 2**32) + 1) / 100)
    return round(min(result, 1000.0), 2)

def safe_room(code):
    r = rooms.get(code)
    if not r:
        return {}
    out = {
        "code":       code,
        "phase":      r["phase"],
        "multiplier": r["multiplier"],
        "countdown":  r["countdown"],
        "players":    r["players"],
        "host":       r["host"],
        "bets": {
            u: {
                "amount":     b["amount"],
                "cashed_out": b["cashed_out"],
                "cashout_at": b["cashout_at"],
            }
            for u, b in r["bets"].items()
        },
    }
    if r["phase"] == "crashed":
        out["crash_at"] = r["crash_at"]
    return out

def bcast(code):
    socketio.emit("crash_state", safe_room(code), to=f"crash_{code}")

def run_room(code):
    with rooms_lock:
        rooms[code]["phase"] = "countdown"
        rooms[code]["countdown"] = 5
    bcast(code)

    for i in range(4, -1, -1):
        sleep(1)
        with rooms_lock:
            if code not in rooms:
                return
            rooms[code]["countdown"] = i
        bcast(code)

    crash_at = generate_crash_point()
    with rooms_lock:
        if code not in rooms:
            return
        rooms[code]["phase"]      = "flying"
        rooms[code]["crash_at"]   = crash_at
        rooms[code]["multiplier"] = 1.00
    bcast(code)

    import time
    start = time.time()
    while True:
        sleep(0.15)
        elapsed = time.time() - start
        current = round(math.exp(0.06 * elapsed), 2)

        with rooms_lock:
            if code not in rooms:
                return
            rooms[code]["multiplier"] = current

            if current >= rooms[code]["crash_at"]:
                rooms[code]["phase"]      = "crashed"
                rooms[code]["multiplier"] = rooms[code]["crash_at"]
                for user, bet in rooms[code]["bets"].items():
                    if not bet["cashed_out"]:
                        record_result(user, "crash", "lose", -bet["amount"])
                bcast(code)
                break

        bcast(code)

    sleep(4)
    with rooms_lock:
        if code not in rooms:
            return
        rooms[code]["phase"]      = "lobby"
        rooms[code]["multiplier"] = 1.00
        rooms[code]["bets"]       = {}
        rooms[code]["countdown"]  = 5
        rooms[code]["greenlet"]   = None
    bcast(code)


@socketio.on("crash_join_room")
def on_join_room(data):
    user = data.get("username") or session.get("username")
    code = data.get("code")
    if not user or not code:
        return
    with rooms_lock:
        if code not in rooms:
            return emit("crash_error", {"msg": "Room not found."})
        r = rooms[code]
        if len(r["players"]) >= MAX_PLAYERS and user not in r["players"]:
            return emit("crash_error", {"msg": "Room is full."})
        if user not in r["players"]:
            r["players"].append(user)
    join_room(f"crash_{code}")
    emit("crash_state", safe_room(code))
    bcast(code)

@socketio.on("crash_leave_room")
def on_leave_room(data):
    user = data.get("username") or session.get("username")
    code = data.get("code")
    if not user or not code:
        return
    with rooms_lock:
        if code not in rooms:
            leave_room(f"crash_{code}")
            return
        r = rooms[code]
        r["players"] = [p for p in r["players"] if p != user]
        if r["host"] == user and r["players"]:
            r["host"] = r["players"][0]
            socketio.emit("crash_state", safe_room(code), to=f"crash_{code}")
        if not r["players"]:
            del rooms[code]
            leave_room(f"crash_{code}")
            return
    leave_room(f"crash_{code}")
    bcast(code)

@socketio.on("crash_start")
def on_start(data):
    user = data.get("username") or session.get("username")
    code = data.get("code")
    if not user or not code:
        return
    with rooms_lock:
        if code not in rooms:
            return emit("crash_error", {"msg": "Room not found."})
        r = rooms[code]
        if r["host"] != user:
            return emit("crash_error", {"msg": "Only the host can start."})
        if r["phase"] != "lobby":
            return emit("crash_error", {"msg": "Round already in progress."})
        if len(r["players"]) < 1:
            return emit("crash_error", {"msg": "Need at least 1 player."})
        g = spawn(run_room, code)
        r["greenlet"] = g
    bcast(code)

@socketio.on("crash_bet")
def on_bet(data):
    user   = data.get("username") or session.get("username")
    code   = data.get("code")
    amount = int(data.get("amount", 0))
    if not user or not code or amount <= 0:
        return emit("crash_error", {"msg": "Invalid bet."})
    with rooms_lock:
        if code not in rooms:
            return emit("crash_error", {"msg": "Room not found."})
        r = rooms[code]
        if r["phase"] not in ("lobby", "countdown"):
            return emit("crash_error", {"msg": "Betting is closed."})
        if user in r["bets"]:
            return emit("crash_error", {"msg": "Already bet this round."})
        chips = get_chips(user)
        if chips < amount:
            return emit("crash_error", {"msg": "Not enough chips."})
        update_chips(user, -amount)
        r["bets"][user] = {
            "amount": amount, "cashed_out": False, "cashout_at": None
        }
    bcast(code)

@socketio.on("crash_cashout")
def on_cashout(data):
    user = data.get("username") or session.get("username")
    code = data.get("code")
    if not user or not code:
        return
    with rooms_lock:
        if code not in rooms:
            return
        r = rooms[code]
        if r["phase"] != "flying":
            return emit("crash_error", {"msg": "Not in flight."})
        bet = r["bets"].get(user)
        if not bet or bet["cashed_out"]:
            return emit("crash_error", {"msg": "Nothing to cash out."})
        mult     = r["multiplier"]
        winnings = int(bet["amount"] * mult)
        bet["cashed_out"] = True
        bet["cashout_at"] = mult
    update_chips(user, winnings)
    record_result(user, "crash", "win", winnings - bet["amount"])
    emit("crash_cashed_out", {"multiplier": mult, "winnings": winnings})
    bcast(code)

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "username" not in session:
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return decorated

@crash_bp.route("/crash")
@login_required
def index():
    username = session["username"]
    return render_template(
        "crash/index.html",
        username=username,
        chips=get_chips(username),
        theme=get_theme(username),
    )

@crash_bp.route("/crash/game")
@login_required
def game():
    code = request.args.get("code")
    username = session["username"]
    if not code or code not in rooms:
        return redirect(url_for("crash.index"))
    return render_template(
        "crash/game.html",
        username=username,
        chips=get_chips(username),
        theme=get_theme(username),
        code=code,
    )

@crash_bp.route("/crash/create", methods=["POST"])
@login_required
def create():
    username = session["username"]
    is_public = request.form.get("public") == "on"
    with rooms_lock:
        for _ in range(10):
            code = str(random.randint(100000, 999999))
            if code not in rooms:
                break
        else:
            return redirect(url_for("crash.index", error="Could not create room."))
        rooms[code] = {
            "players":    [username],
            "phase":      "lobby",
            "multiplier": 1.00,
            "crash_at":   1.00,
            "bets":       {},
            "countdown":  5,
            "host":       username,
            "public":     is_public,
            "greenlet":   None,
        }
    return redirect(url_for("crash.game", code=code))

@crash_bp.route("/crash/join", methods=["POST"])
@login_required
def join():
    username = session["username"]
    code = request.form.get("code", "").strip()
    with rooms_lock:
        if code not in rooms:
            return redirect(url_for("crash.index", error="Room not found."))
        r = rooms[code]
        if r["phase"] not in ("lobby", "countdown"):
            return redirect(url_for("crash.index", error="Round already in progress."))
        if len(r["players"]) >= MAX_PLAYERS:
            return redirect(url_for("crash.index", error="Room is full."))
        if username not in r["players"]:
            r["players"].append(username)
    return redirect(url_for("crash.game", code=code))

@crash_bp.route("/crash/rooms")
@login_required
def public_rooms():
    with rooms_lock:
        result = [
            {"code": c, "players": len(r["players"]), "host": r["host"], "phase": r["phase"]}
            for c, r in rooms.items() if r.get("public")
        ]
    return {"rooms": result}