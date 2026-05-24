from flask import Blueprint, request, session, render_template, redirect, url_for
from flask_socketio import join_room, emit
from functools import wraps
from auth.auth import get_theme, record_result, record_played_with_all
import json, os, random, re, threading

from core import app, socketio

enraged_bp = Blueprint(
    'enraged',
    __name__,
    template_folder='templates',
    static_folder='static',
    static_url_path='/enraged/static'
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
GAME_FILE = os.path.join(BASE_DIR, "enraged_game.json")
MAX_PLAYERS = 5

file_lock = threading.RLock()

def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if "username" not in session:
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return decorated

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

def get_rank(c):
    return re.sub(r'[^0-9JQKA]', '', c) if "JOKER" not in c else "JOKER"

def value(c, ace_high=True):
    r = get_rank(c)
    if r == "JOKER": return 0
    if r == "A": return 14 if ace_high else 1
    return {"J": 11, "Q": 12, "K": 13}.get(r, int(r) if r.isdigit() else 0)

def effective_top(g):
    for c in reversed(g["pile"]):
        if get_rank(c) not in ("3", "JOKER"):
            return c
    return None

SUITS = ["H", "D", "C", "S"]
RANKS = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]

def make_deck():
    deck = [r + s for s in SUITS for r in RANKS]
    deck += ["JOKER1", "JOKER2"]  # 2 jokers
    random.shuffle(deck)
    return deck

def effective_top_value(g):
    top = effective_top(g)
    if top is None:
        return None, None
    r = get_rank(top)
    if r == "A":
        v = 14 if g.get("aceMode", "high") == "high" else 1
        return v, r
    return value(top), r

def valid_move(g, cards):
    if not cards:
        return False
    ranks = [get_rank(c) for c in cards]
    if len(set(ranks)) != 1:
        return False
    r = ranks[0]
    top_v, top_r = effective_top_value(g)

    if r in ("2", "3", "JOKER"):
        return True
    if r == "10":
        return not g.get("sevenRule")
    if r == "8":
        if g.get("sevenRule"):
            return False
        return top_v is None or top_v <= 8
    if g.get("sevenRule"):
        if r == "A":
            return True
        return value(cards[0]) <= 7
    if r == "A":
        return True
    card_v = value(cards[0])
    if top_v is not None and card_v < top_v:
        return False
    return True

def valid_move_with_ace(g, cards, ace_mode):
    r = get_rank(cards[0]) if cards else None
    if r != "A":
        return valid_move(g, cards)
    top_v, _ = effective_top_value(g)
    if g.get("sevenRule"):
        return ace_mode == "low"
    if top_v is None:
        return True
    ace_v = 1 if ace_mode == "low" else 14
    return ace_v >= top_v

def apply_jokers(g, count):
    players = g["players"]
    n = len(players)
    if n < 2:
        return
    old_piles = {p: g["piles"].get(p, [])[:] for p in players}
    for i, p in enumerate(players):
        donor = players[(i - count) % n]
        g["piles"][p] = old_piles[donor]

def next_player(g, cur):
    if not g["players"]:
        return
    i = g["players"].index(cur)
    g["turn"] = g["players"][(i + 1) % len(g["players"])]

def next_player_n(g, cur, n):
    if not g["players"]:
        return
    i = g["players"].index(cur)
    g["turn"] = g["players"][(i + n) % len(g["players"])]

def pickup_pile(g, user):
    g["piles"][user] = g["piles"].get(user, []) + g["pile"]
    g["pile"] = []
    g["afterTwo"] = False
    g["sevenRule"] = False
    g["aceMode"] = "high"

def check_win(g, p):
    if not g["piles"].get(p):
        position = len(g["dead"])
        result = "win" if position == 0 else "lose"
        record_result(p, "enraged", result, 0)
        g["players"].remove(p)
        g["dead"].append(p)
        return True
    return False

def record_pile_history(g, cards):
    history = g.setdefault("pileHistory", [])
    r = get_rank(cards[0])
    if r != "3":
        entry = {
            "cards": cards[:],
            "rank": r,
            "aceMode": g.get("aceMode", "high") if r == "A" else None
        }
        history.append(entry)
        g["pileHistory"] = history[-5:]


@socketio.on("enraged_join")
def enraged_join(data):
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
    socketio.emit("enraged_state", g, to=code)


@socketio.on("enraged_start")
def enraged_start(data):
    games = load_json(GAME_FILE)

    code = data["code"]
    g = games["games"].get(code)
    if not g:
        return

    deck = make_deck()
    random.shuffle(deck)

    n = len(g["players"])
    per_player = len(deck) // n
    piles = {}
    for i, p in enumerate(g["players"]):
        piles[p] = deck[i * per_player:(i + 1) * per_player]

    g.update({
        "piles": piles,
        "pile": [],
        "pileHistory": [],
        "afterTwo": False,
        "sevenRule": False,
        "aceMode": "high",
        "dead": [],
        "phase": "playing",
        "turn": g["players"][0],
        "shuffledThisTurn": False,
        "pendingSkip": 0,
    })

    save_json(GAME_FILE, games)
    socketio.emit("enraged_state", g, to=code)


@socketio.on("enraged_play")
def enraged_play(data):
    games = load_json(GAME_FILE)
    code = data["code"]
    user = data.get("username")
    ace_choice = data.get("aceMode", "high")

    g = games["games"].get(code)
    if not g or g.get("phase") != "playing":
        return
    if g["turn"] != user or user not in g["players"]:
        return

    pile = g["piles"].get(user, [])
    if not pile:
        return

    card = pile[-1]
    cards = [card]
    r = get_rank(card)

    if r == "JOKER":
        pile.pop()
        g["piles"][user] = pile
        g["pile"].append(card)
        apply_jokers(g, 1)
        won = check_win(g, user)
        if not won:
            next_player(g, user)
        g["shuffledThisTurn"] = False
        if len(g["players"]) <= 1:
            record_played_with_all(list(g["dead"]) + g["players"])
        save_json(GAME_FILE, games)
        socketio.emit("enraged_state", g, to=code)
        return

    if r == "A":
        move_ok = valid_move_with_ace(g, cards, ace_choice)
    else:
        move_ok = valid_move(g, cards)

    if not move_ok:
        pile.pop()
        g["piles"][user] = pile
        g["pile"].append(card)
        pickup_pile(g, user)
        g["shuffledThisTurn"] = False
        next_player(g, user)
        save_json(GAME_FILE, games)
        socketio.emit("enraged_state", g, to=code)
        socketio.emit("enraged_invalid", {"msg": "Can't play that — picked up the pile!"}, to=request.sid)
        return

    pile.pop()
    g["piles"][user] = pile
    record_pile_history(g, cards)

    extra_turn = False
    burn = False

    if r == "2":
        g["pile"].append(card)
        g["afterTwo"] = True
        g["sevenRule"] = False
        g["aceMode"] = "high"
    elif r == "3":
        g["pile"].append(card)
    elif r == "7":
        g["pile"].append(card)
        g["sevenRule"] = True
        g["afterTwo"] = False
        g["aceMode"] = "high"
    elif r == "8":
        g["pile"].append(card)
        g["sevenRule"] = False
        g["afterTwo"] = False
        g["pendingSkip"] = g.get("pendingSkip", 0) + 1
    elif r == "10":
        g["pile"].append(card)
        g["pile"] = []
        g["pileHistory"] = []
        g["afterTwo"] = False
        g["sevenRule"] = False
        g["aceMode"] = "high"
        burn = True
        extra_turn = True
    elif r == "A":
        g["pile"].append(card)
        g["aceMode"] = ace_choice
        g["afterTwo"] = False
        g["sevenRule"] = False
    else:
        g["pile"].append(card)
        g["afterTwo"] = False
        g["sevenRule"] = False
        g["aceMode"] = "high"

    if not burn and len(g["pile"]) >= 4:
        top4 = g["pile"][-4:]
        if len(set(get_rank(c) for c in top4)) == 1:
            g["pile"] = []
            g["pileHistory"] = []
            g["afterTwo"] = False
            g["sevenRule"] = False
            g["aceMode"] = "high"
            extra_turn = True

    players_before = g["players"][:]
    idx = players_before.index(user)
    next_p = players_before[(idx + 1) % len(players_before)]

    won = check_win(g, user)
    g["shuffledThisTurn"] = False

    if won:
        if g["players"]:
            g["turn"] = next_p if next_p in g["players"] else g["players"][0]
    elif extra_turn:
        pass
    else:
        skip = g.pop("pendingSkip", 0)
        if skip > 0:
            n = len(g["players"])
            net = skip % n
            if net != 0:
                next_player_n(g, user, net + 1)
            else:
                next_player(g, user)
        else:
            next_player(g, user)

    if len(g["players"]) <= 1:
        record_played_with_all(list(g["dead"]) + g["players"])

    save_json(GAME_FILE, games)
    socketio.emit("enraged_state", g, to=code)


@socketio.on("enraged_shuffle")
def enraged_shuffle(data):
    games = load_json(GAME_FILE)
    code = data["code"]
    user = data.get("username")
    g = games["games"].get(code)

    if not g or g.get("phase") != "playing":
        return
    if g["turn"] != user:
        return
    if g.get("shuffledThisTurn"):
        socketio.emit("enraged_invalid", {"msg": "Already shuffled this turn!"}, to=request.sid)
        return

    pile = g["piles"].get(user, [])
    random.shuffle(pile)
    g["piles"][user] = pile
    g["shuffledThisTurn"] = True

    save_json(GAME_FILE, games)
    socketio.emit("enraged_state", g, to=code)


@socketio.on("enraged_pickup")
def enraged_pickup(data):
    games = load_json(GAME_FILE)
    code = data["code"]
    user = data.get("username")
    g = games["games"].get(code)

    if not g or g["turn"] != user:
        return

    pickup_pile(g, user)
    g["shuffledThisTurn"] = False
    next_player(g, user)
    save_json(GAME_FILE, games)
    socketio.emit("enraged_state", g, to=code)


@socketio.on('enraged_game_msg')
def handle_enraged_msg(data):
    if session.get("username"):
        code = data.get("code")
        emit('enraged_receive_msg', {
            'sender': session.get("username"),
            'msg': data['msg'],
        }, to=code)



@enraged_bp.route("/enraged", methods=["GET", "POST"])
@login_required
def index():
    username = session["username"]
    games = load_json(GAME_FILE)

    if request.method == "POST":
        if "create" in request.form:
            code = str(random.randint(100000, 999999))
            is_public = "public" in request.form
            games.setdefault("games", {})[code] = {
                "players": [],
                "piles": {},
                "pile": [],
                "pileHistory": [],
                "turn": None,
                "afterTwo": False,
                "sevenRule": False,
                "aceMode": "high",
                "dead": [],
                "phase": "lobby",
                "public": is_public,
                "shuffledThisTurn": False,
                "pendingSkip": 0,
            }
            save_json(GAME_FILE, games)
            return redirect(url_for("enraged.game", theme=get_theme(username), code=code))

        if "join" in request.form:
            code = request.form.get("room_code", "").strip()
            if code in games.get("games", {}):
                room = games["games"][code]
                if username in room["players"]:
                    return render_template("enraged/index.html",
                        theme=get_theme(username),
                        error=f'"{username}" is already in room {code}.',
                        username=username)
                if len(room["players"]) >= MAX_PLAYERS:
                    return render_template("enraged/index.html",
                        theme=get_theme(username),
                        error="Room is full (max 5).",
                        username=username)
                room["players"].append(username)
                save_json(GAME_FILE, games)
                return redirect(url_for("enraged.game", theme=get_theme(username), code=code))
            else:
                return render_template("enraged/index.html",
                    theme=get_theme(username),
                    error="Room not found.",
                    username=username)

    return render_template("enraged/index.html", theme=get_theme(username), username=username)


@enraged_bp.route("/enraged/rooms")
@login_required
def public_rooms():
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


@enraged_bp.route("/enraged/game")
@login_required
def game():
    code = request.args.get("code")
    username = session.get("username")
    if not code or not username:
        return redirect(url_for("enraged.index"))
    return render_template("enraged/game.html",
        theme=get_theme(username),
        roomCode=code,
        username=username)