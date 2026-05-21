from flask import Blueprint, request, session, render_template, redirect, url_for
from flask_socketio import join_room, emit 
import json, os, random, threading
from auth.auth import record_result
from functools import wraps
from auth.auth import record_result, record_played_with_all, get_theme
from core import socketio

sevens_bp = Blueprint(
    'sevens',
    __name__,
    template_folder='templates',
    static_folder='static',
    static_url_path='/sevens/static'
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
GAME_FILE = os.path.join(BASE_DIR, "game.json")
MAX_PLAYERS = 6

file_lock = threading.RLock()

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "username" not in session:
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return decorated

SUITS = ["H", "D", "C", "S"]
RANKS = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]
RANK_VALUE = {r: i for i, r in enumerate(RANKS)}

def make_deck():
    return [r + s for s in SUITS for r in RANKS]

def get_rank(c):
    return c[:-1]

def get_suit(c):
    return c[-1]

def load_json(p):
    with file_lock:
        if not os.path.exists(p):
            return {}
        try:
            with open(p) as f:
                content = f.read()
                if not content.strip():
                    return {}
                return json.loads(content)
        except json.JSONDecodeError:
            return {}

def save_json(p, d):
    with file_lock:
        with open(p, "w") as f:
            json.dump(d, f, indent=4)

def can_play(board, card):
    r = get_rank(card)
    s = get_suit(card)
    rv = RANK_VALUE[r]

    if r == "7":
        return True

    suit_state = board.get(s)
    if not suit_state:
        return False

    low = suit_state["low"]
    high = suit_state["high"]

    return rv == low - 1 or rv == high + 1

def get_playable(board, hand):
    return [c for c in hand if can_play(board, c)]

def next_player(g, cur):
    players = g["players"]
    if not players:
        return
    i = players.index(cur)
    g["turn"] = players[(i + 1) % len(players)]

def check_win(g, p):
    if not g["hands"].get(p):
        position = len(g["finished"])
        result = "win" if position == 0 else "lose"
        record_result(p, "sevens", result, 0)
        g["players"].remove(p)
        g["finished"].append(p)
        g["hands"].pop(p, None)
        return True
    return False


@socketio.on("sevens_join")
def sevens_join(data):
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
    socketio.emit("sevens_state", g, to=code)


@socketio.on("sevens_start")
def sevens_start(data):
    code = data["code"]
    games = load_json(GAME_FILE)
    g = games["games"].get(code)
    if not g:
        return

    deck = make_deck()
    random.shuffle(deck)

    hands = {p: [] for p in g["players"]}
    for i, card in enumerate(deck):
        hands[g["players"][i % len(g["players"])]].append(card)

    first = g["players"][0]
    for p, h in hands.items():
        if "7D" in h:
            first = p
            break

    g.update({
        "hands": hands,
        "board": {},
        "completed": [],
        "finished": [],
        "turn": first,
        "phase": "playing",
        "passed": [],
    })

    save_json(GAME_FILE, games)
    socketio.emit("sevens_state", g, to=code)


@socketio.on("sevens_play")
def sevens_play(data):
    code = data["code"]
    user = data["username"]
    card = data["card"]

    games = load_json(GAME_FILE)
    g = games["games"].get(code)
    if not g or g.get("phase") != "playing":
        return
    if g["turn"] != user or user not in g["players"]:
        return

    hand = g["hands"].get(user, [])
    if card not in hand:
        socketio.emit("sevens_invalid", {"msg": "You don't have that card!"}, to=request.sid)
        return

    if not can_play(g["board"], card):
        socketio.emit("sevens_invalid", {"msg": "You can't play that card!"}, to=request.sid)
        return

    if not g["board"] and card != "7D":
        socketio.emit("sevens_invalid", {"msg": "The first card must be the 7 of Diamonds!"}, to=request.sid)
        return
    hand.remove(card)
    g["hands"][user] = hand

    r = get_rank(card)
    s = get_suit(card)
    rv = RANK_VALUE[r]

    if r == "7":
        g["board"][s] = {"low": 6, "high": 6}
    else:
        suit_state = g["board"][s]
        if rv < suit_state["low"]:
            suit_state["low"] = rv
        else:
            suit_state["high"] = rv
        g["board"][s] = suit_state

    suit_complete = False
    ss = g["board"].get(s, {})
    if ss.get("low") == 0 and ss.get("high") == 12:
        if s not in g.get("completed", []):
            g.setdefault("completed", []).append(s)
            suit_complete = True

    g["passed"] = []

    players_before = g["players"][:]
    idx = players_before.index(user)
    next_p = players_before[(idx + 1) % len(players_before)]

    won = check_win(g, user)

    if len(g["players"]) == 0:
        g["phase"] = "done"
    elif len(g["players"]) == 1:
        last = g["players"][0]
        g["players"].remove(last)
        g["finished"].append(last)
        g["hands"].pop(last, None)
        g["phase"] = "done"
    else:
        if won:
            g["turn"] = next_p if next_p in g["players"] else g["players"][0]
        elif suit_complete:
            pass
        else:
            next_player(g, user)

    if len(g["players"]) == 0:
        g["phase"] = "done"
        all_players = g["finished"]
        all_players = list(g["dead"]) + g["players"]
        record_played_with_all(all_players)
    elif len(g["players"]) == 1:
        last = g["players"][0]
        g["players"].remove(last)
        g["finished"].append(last)
        g["hands"].pop(last, None)
        g["phase"] = "done"
        all_players = g["finished"]
        all_players = list(g["dead"]) + g["players"]
        record_played_with_all(all_players)
        
    save_json(GAME_FILE, games)
    socketio.emit("sevens_state", g, to=code)


@socketio.on("sevens_pass")
def sevens_pass(data):
    code = data["code"]
    user = data["username"]

    games = load_json(GAME_FILE)
    g = games["games"].get(code)
    if not g or g.get("phase") != "playing":
        return
    if g["turn"] != user or user not in g["players"]:
        return

    hand = g["hands"].get(user, [])
    if get_playable(g["board"], hand):
        socketio.emit("sevens_invalid", {"msg": "You must play — you have a valid card!"}, to=request.sid)
        return

    if user not in g["passed"]:
        g["passed"].append(user)

    next_player(g, user)
    save_json(GAME_FILE, games)
    socketio.emit("sevens_state", g, to=code)

@socketio.on('send_7game_msg')
def handle_global(data):
    if session.get("username"):
        code = data.get("code")
        emit('receive_7game_msg', {
            'sender': session.get("username"),
            'msg': data['msg'],
            'type': 'global'
        }, to=code)

def get_public_rooms(games):
    return [
        (code, room) for code, room in games.get("games", {}).items()
        if room.get("is_public") and room.get("phase") == "lobby"
        and len(room["players"]) < MAX_PLAYERS
    ]

@sevens_bp.route("/sevens", methods=["GET", "POST"])
@login_required
def index():
    username = session["username"]

    if request.method == "POST":
        games = load_json(GAME_FILE)

        if "create" in request.form:
            code = str(random.randint(100000, 999999))
            is_public = "is_public" in request.form
            games.setdefault("games", {})[code] = {
                "players": [],
                "hands": {},
                "board": {},
                "completed": [],
                "finished": [],
                "turn": None,
                "phase": "lobby",
                "passed": [],
                "is_public": is_public,
            }
            save_json(GAME_FILE, games)
            return redirect(url_for("sevens.game", code=code))

        if "join" in request.form:
            code = request.form.get("room_code", "").strip()
            if code in games.get("games", {}):
                room = games["games"][code]
                if username in room["players"]:
                    return render_template("sevens/index.html",
                        error=f'The name "{username}" is already taken in room {code}.',
                        username=username,
                        theme=get_theme(username),
                        public_rooms=get_public_rooms(games))
                if len(room["players"]) >= MAX_PLAYERS:
                    return render_template("sevens/index.html",
                        error="That room is full (max 6 players).",
                        username=username,
                        theme=get_theme(username),
                        public_rooms=get_public_rooms(games))
                room["players"].append(username)
                save_json(GAME_FILE, games)
                return redirect(url_for("sevens.game", code=code))
            else:
                return render_template("sevens/index.html",
                    error="Room not found.",
                    username=username,
                    theme=get_theme(username),
                    public_rooms=get_public_rooms(games))
    games = load_json(GAME_FILE)
    return render_template("sevens/index.html",
        username=username,
        theme=get_theme(username),
        public_rooms=get_public_rooms(games))

@sevens_bp.route("/sevens/game")
@login_required
def game():
    code = request.args.get("code")
    username = session["username"]
    if not code or not username:
        return redirect(url_for("sevens.index"))
    return render_template("sevens/game.html", theme=get_theme(username), roomCode=code, username=username)