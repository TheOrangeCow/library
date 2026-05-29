import hashlib, hmac, os, time, threading, random
from flask import Blueprint, session, redirect, url_for, render_template, request
from flask_socketio import join_room, emit
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


ROOM = "crash_table"

state = {
    "phase": "waiting",
    "multiplier": 1.00,
    "crash_at": 1.00,
    "bets": {},
    "countdown": 5,
}
state_lock = threading.Lock()
game_thread = None


def generate_crash_point(seed: str | None = None) -> float:
    if seed is None:
        seed = os.urandom(16).hex()
    h = hmac.new(seed.encode(), b"crash", hashlib.sha256).hexdigest()
    n = int(h[:8], 16)
    if n % 33 == 0:
        return 1.00
    result = max(1.00, (100 * 2**32) / ((n % 2**32) + 1) / 100)
    return round(min(result, 1000.0), 2)


def broadcast(event: str, data: dict):
    socketio.emit(event, data, to=ROOM)


def run_game():
    global state

    while True:
        with state_lock:
            state["phase"]      = "waiting"
            state["multiplier"] = 1.00
            state["bets"]       = {}
            state["countdown"]  = 5
        broadcast("crash_state", safe_state())
        time.sleep(1)

        with state_lock:
            state["phase"] = "countdown"
        for i in range(5, 0, -1):
            with state_lock:
                state["countdown"] = i
            broadcast("crash_state", safe_state())
            time.sleep(1)

        crash_at = generate_crash_point()
        with state_lock:
            state["phase"]     = "flying"
            state["crash_at"]  = crash_at
            state["multiplier"] = 1.00
        broadcast("crash_state", safe_state())

        start = time.time()
        while True:
            elapsed   = time.time() - start
            import math
            current = round(1.00 * math.exp(0.06 * elapsed), 2)

            with state_lock:
                state["multiplier"] = current
                if current >= state["crash_at"]:
                    state["phase"]     = "crashed"
                    state["multiplier"] = state["crash_at"]
                    for user, bet in state["bets"].items():
                        if not bet["cashed_out"]:
                            record_result(user, "crash", "lose", -bet["amount"])
                    broadcast("crash_state", safe_state())
                    break

            broadcast("crash_state", safe_state())
            time.sleep(0.15)

        time.sleep(4)


def safe_state() -> dict:
    """Return a copy of state safe to send to clients (no crash_at spoiler)."""
    with state_lock:
        out = {
            "phase":      state["phase"],
            "multiplier": state["multiplier"],
            "countdown":  state["countdown"],
            "bets":       {
                u: {
                    "amount":     b["amount"],
                    "cashed_out": b["cashed_out"],
                    "cashout_at": b["cashout_at"],
                }
                for u, b in state["bets"].items()
            },
        }
        if state["phase"] == "crashed":
            out["crash_at"] = state["crash_at"]
    return out

@socketio.on("crash_join")
def on_join(data):
    user = data.get("username") or session.get("username")
    if not user:
        return
    join_room(ROOM)
    emit("crash_state", safe_state())


@socketio.on("crash_bet")
def on_bet(data):
    user   = data.get("username") or session.get("username")
    amount = int(data.get("amount", 0))

    if not user or amount <= 0:
        return emit("crash_error", {"msg": "Invalid bet."})

    with state_lock:
        phase = state["phase"]
        if phase not in ("waiting", "countdown"):
            return emit("crash_error", {"msg": "Betting is closed."})
        if user in state["bets"]:
            return emit("crash_error", {"msg": "Already bet this round."})

    chips = get_chips(user)
    if chips < amount:
        return emit("crash_error", {"msg": "Not enough chips."})
    update_chips(user, -amount)

    with state_lock:
        state["bets"][user] = {
            "amount":     amount,
            "cashed_out": False,
            "cashout_at": None,
        }

    broadcast("crash_state", safe_state())


@socketio.on("crash_cashout")
def on_cashout(data):
    user = data.get("username") or session.get("username")
    if not user:
        return

    with state_lock:
        if state["phase"] != "flying":
            return emit("crash_error", {"msg": "Not in flight."})
        bet = state["bets"].get(user)
        if not bet or bet["cashed_out"]:
            return emit("crash_error", {"msg": "Nothing to cash out."})

        mult       = state["multiplier"]
        winnings   = int(bet["amount"] * mult)
        bet["cashed_out"] = True
        bet["cashout_at"] = mult

    update_chips(user, winnings)
    record_result(user, "crash", "win", winnings - bet["amount"])
    emit("crash_cashed_out", {"multiplier": mult, "winnings": winnings})
    broadcast("crash_state", safe_state())


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
        "crash/game.html",
        username=username,
        chips=get_chips(username),
        theme=get_theme(username),
    )


def start_game_thread():
    global game_thread
    if game_thread is None or not game_thread.is_alive():
        game_thread = threading.Thread(target=run_game, daemon=True)
        game_thread.start()