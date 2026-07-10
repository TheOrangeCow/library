"""from flask import Flask, request, session, render_template, redirect, url_for
from flask_socketio import SocketIO, join_room, emit
import json, os, random, re, threading, time
from flask import Blueprint
from functools import wraps
from auth.auth import record_result, get_theme, is_plus
from auth.auth import record_result, record_played_with_all

if __name__ == "main":
    app = Flask(__name__)
    app.secret_key = "secret_key"
    socketio = SocketIO(app, cors_allowed_origins="*")
else:
    from core import app, socketio

ratscrew_bp = Blueprint(
    'ratscrew',
    __name__,
    template_folder='templates',
    static_folder='static',
    static_url_path='/ratscrew/static'
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
GAME_FILE = os.path.join(BASE_DIR, "game.json")
MAX_PLAYERS = 6

FACE_NEEDS = {"J": 1, "Q": 2, "K": 3, "A": 4}
SLAP_BURN_DELAY = 0 


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "username" not in session:
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return decorated


file_lock = threading.RLock()


def load_json(p):
    with file_lock:
        if not os.path.exists(p):
            return {}
        try:
            with open(p) as f:
                content = f.read()
                if not content.strip():
                    return {}
                data = json.loads(content)
        except json.JSONDecodeError:
            return {}

    if "games" in data:
        if prune_expired_games(data):
            save_json(p, data)

    return data


def save_json(p, d):
    with file_lock:
        with open(p, "w") as f:
            json.dump(d, f, indent=4)


LOBBY_TTL = 30 * 60
GAME_TTL = 24 * 60 * 60


def prune_expired_games(games):
    now = time.time()
    to_delete = []
    for code, g in games.get("games", {}).items():
        created = g.get("created_at", now)
        phase = g.get("phase", "lobby")
        ttl = LOBBY_TTL if phase == "lobby" else GAME_TTL
        if now - created > ttl:
            to_delete.append(code)
    for code in to_delete:
        del games["games"][code]
    return bool(to_delete)


def get_rank(c):
    return re.sub(r'[^0-9JQKA]', '', c)


def fresh_deck():
    ranks = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"]
    suits = ["H", "D", "C", "S"]
    return [f"{r}{s}" for r in ranks for s in suits]


def next_player(g, cur):
    living = g["players"]
    if not living:
        return
    i = living.index(cur) if cur in living else -1
    g["turn"] = living[(i + 1) % len(living)]


def award_pile(g, winner):
    pile = g["center"]
    g["center"] = []
    g["piles"].setdefault(winner, [])
    g["piles"][winner] = pile + g["piles"][winner]
    g["challenge"] = None
    g["turn"] = winner


def is_slappable(center):
    if len(center) >= 2 and get_rank(center[-1]) == get_rank(center[-2]):
        return True
    if len(center) >= 3 and get_rank(center[-1]) == get_rank(center[-3]):
        return True
    return False


def advance_to_next_living(g):
    guard = 0
    while g["players"] and guard < 20:
        guard += 1
        cur = g.get("turn")

        if cur is None or cur not in g["players"]:
            g["turn"] = g["players"][0]
            cur = g["turn"]

        if g["piles"].get(cur):
            break

        idx = g["players"].index(cur)
        successor = g["players"][(idx + 1) % len(g["players"])] if len(g["players"]) > 1 else None
        g["players"].remove(cur)
        g["dead"].append(cur)
        if len(g["players"]) >= 1:
            record_result(cur, "ratscrew", "lose", 0)

        if not g["players"]:
            g["turn"] = None
            break

        g["turn"] = successor if successor in g["players"] else g["players"][0]

    if len(g["players"]) == 1 and g.get("phase") == "playing":
        winner = g["players"][0]
        record_result(winner, "ratscrew", "win", 0)
        all_players = list(g["dead"]) + g["players"]
        record_played_with_all(all_players)
        g["phase"] = "over"
        g["winner"] = winner


swap_timers = {}


def trigger_bot_if_needed(code):
    games = load_json(GAME_FILE)
    g = games["games"].get(code)
    if not g or g.get("phase") != "playing":
        return
    turn = g.get("turn")
    if turn and turn in g.get("bots", []):
        t = threading.Thread(target=bot_play, args=[code], daemon=True)
        t.start()
    if g.get("bots"):
        t2 = threading.Thread(target=bot_try_slap, args=[code], daemon=True)
        t2.start()


def bot_play(code):
    time.sleep(1.0)
    games = load_json(GAME_FILE)
    g = games["games"].get(code)
    if not g or g.get("phase") != "playing":
        return
    bot = g.get("turn")
    if not bot or bot not in g.get("bots", []):
        return
    _do_play(code, bot)


def bot_try_slap(code):
    time.sleep(random.uniform(0.4, 1.6))
    games = load_json(GAME_FILE)
    g = games["games"].get(code)
    if not g or g.get("phase") != "playing":
        return
    for bot in g.get("bots", []):
        if bot not in g.get("players", []):
            continue
        if is_slappable(g.get("center", [])):
            _do_slap(code, bot)
            return


def _do_play(code, user):
    games = load_json(GAME_FILE)
    g = games["games"].get(code)
    if not g or g.get("phase") != "playing":
        return
    if g.get("turn") != user or user not in g["players"]:
        return

    pile = g["piles"].get(user, [])
    if not pile:
        advance_to_next_living(g)
        save_json(GAME_FILE, games)
        socketio.emit("state", g, to=code)
        trigger_bot_if_needed(code)
        return

    card = pile.pop(0)
    g["piles"][user] = pile
    g["center"].append(card)
    rank = get_rank(card)

    if rank in FACE_NEEDS:
        g["challenge"] = {"active": True, "count": FACE_NEEDS[rank], "owner": user, "rank": rank}
        next_player(g, user)
    else:
        ch = g.get("challenge")
        if ch and ch.get("active"):
            ch["count"] -= 1
            if ch["count"] <= 0:
                award_pile(g, ch["owner"])
            else:
                next_player(g, user)
        else:
            next_player(g, user)

    advance_to_next_living(g)
    save_json(GAME_FILE, games)
    socketio.emit("state", g, to=code)
    trigger_bot_if_needed(code)


def _do_slap(code, user):
    games = load_json(GAME_FILE)
    g = games["games"].get(code)
    if not g or g.get("phase") != "playing":
        return
    if user not in g["players"]:
        return

    center = g.get("center", [])
    if is_slappable(center):
        g["center"] = []
        g["piles"].setdefault(user, [])
        g["piles"][user] = center + g["piles"][user]
        g["challenge"] = None
        next_player(g, user)
        socketio.emit("slapResult", {"user": user, "success": True}, to=code)
    else:
        my_pile = g["piles"].get(user, [])
        if my_pile:
            burned = my_pile.pop(0)
            g["piles"][user] = my_pile
            g["center"].append(burned)
        socketio.emit("slapResult", {"user": user, "success": False}, to=code)

    advance_to_next_living(g)
    save_json(GAME_FILE, games)
    socketio.emit("state", g, to=code)
    trigger_bot_if_needed(code)


@socketio.on("add_bot")
def add_bot(data):
    games = load_json(GAME_FILE)
    code = data["code"]
    g = games["games"].get(code)
    if not g or g.get("phase") != "lobby":
        return
    if len(g["players"]) >= MAX_PLAYERS:
        return
    bot_num = sum(1 for p in g["players"] if p.startswith("BOT_")) + 1
    bot_name = f"BOT_{bot_num}"
    g["players"].append(bot_name)
    g.setdefault("bots", []).append(bot_name)
    save_json(GAME_FILE, games)
    socketio.emit("state", g, to=code)


@socketio.on("join")
def join(data):
    code = data["code"]
    user = data["username"]
    if not user or not code:
        return
    games = load_json(GAME_FILE)
    g = games["games"].get(code)
    if not g:
        return
    if user not in g["players"]:
        g["players"].append(user)
    save_json(GAME_FILE, games)
    join_room(code)
    socketio.emit("state", g, to=code)


@socketio.on("start")
def start(data):
    games = load_json(GAME_FILE)
    code = data["code"]
    g = games["games"][code]

    deck = fresh_deck()
    random.shuffle(deck)

    players = g["players"]
    piles = {p: [] for p in players}
    i = 0
    for c in deck:
        piles[players[i % len(players)]].append(c)
        i += 1

    g.update({
        "piles": piles,
        "center": [],
        "challenge": None,
        "dead": [],
        "phase": "playing",
        "winner": None,
        "turn": players[0],
    })

    save_json(GAME_FILE, games)
    socketio.emit("state", g, to=code)
    trigger_bot_if_needed(code)


@socketio.on("play")
def play(data):
    _do_play(data["code"], data.get("username"))


@socketio.on("slap")
def slap(data):
    _do_slap(data["code"], data.get("username"))


@socketio.on('send_game_msg')
def handle_global(data):
    if session.get("username"):
        code = data.get("code")
        emit('receive_game_msg', {
            'sender': session.get("username"),
            'msg': data['msg'],
            'type': 'global'
        }, to=code)


@app.route("/ratscrew", methods=["GET", "POST"])
@login_required
def ratscrew_index():
    games = load_json(GAME_FILE)
    username = session["username"]
    if not is_plus(username):
        return redirect("https://library.theorangecow.org/plus?upgrade=true")
    if request.method == "POST":

        if "create" in request.form:
            code = str(random.randint(100000, 999999))
            is_public = "public" in request.form

            games.setdefault("games", {})[code] = {
                "players": [],
                "bots": [],
                "piles": {},
                "center": [],
                "turn": None,
                "challenge": None,
                "dead": [],
                "phase": "lobby",
                "winner": None,
                "public": is_public,
                "created_at": time.time(),
            }
            save_json(GAME_FILE, games)
            return redirect(url_for("ratscrew_game", theme=get_theme(username), code=code))

        if "join" in request.form:
            code = request.form.get("room_code")
            if code in games.get("games", {}):
                room = games["games"][code]
                if username in room["players"]:
                    return render_template("/ratscrew/index.html", theme=get_theme(username),
                                            error=f'The name "{username}" is already taken in room {code}.',
                                            username=username)
                if len(room["players"]) >= MAX_PLAYERS:
                    return render_template("/ratscrew/index.html", theme=get_theme(username),
                                            error="That room is full (max 6 players).", username=username)
                room["players"].append(username)
                save_json(GAME_FILE, games)
                return redirect(url_for("ratscrew_game", theme=get_theme(username), code=code))

    return render_template("/ratscrew/index.html", theme=get_theme(username), username=username)


@app.route("/ratscrew/rooms")
@login_required
def ratscrew_public_rooms():
    username = session["username"]
    if not is_plus(username):
        return redirect("https://library.theorangecow.org/plus?upgrade=true")
    games = load_json(GAME_FILE)
    rooms = []
    for code, g in games.get("games", {}).items():
        if g.get("public") and g.get("phase") == "lobby":
            rooms.append({
                "code": code,
                "players": len(g["players"]),
                "max": MAX_PLAYERS,
                "names": g["players"]
            })
    return {"rooms": rooms}


@app.route("/ratscrew/game")
@login_required
def ratscrew_game():
    code = request.args.get("code")
    username = session.get("username")
    if not is_plus(username):
        return redirect("https://library.theorangecow.org/plus?upgrade=true")
    if not code or not username:
        return redirect(url_for("ratscrew_index"))
    return render_template(
        "/ratscrew/game.html",
        roomCode=code,
        theme=get_theme(username),
        username=username
    )"""