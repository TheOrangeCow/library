from flask import Flask, request, session, render_template, redirect, url_for
from flask_socketio import SocketIO, join_room
import json, os, random, re, threading
from flask import Blueprint
from functools import wraps
from auth.auth import record_result
from auth.auth import record_result, record_played_with_all

if __name__ == "main":
    app = Flask(__name__)
    app.secret_key = "secret_key"
    socketio = SocketIO(app, cors_allowed_origins="*")
else:
    from core import app, socketio 

pooheads_bp = Blueprint(
    'pooheads',
    __name__,
    template_folder='templates',
    static_folder='static',
    static_url_path='/pooheads/static'
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
GAME_FILE = os.path.join(BASE_DIR, "game.json")
CARDS_FILE = os.path.join(BASE_DIR, "cards.json")
MAX_PLAYERS = 5

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "username" not in session:
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return decorated

import threading
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
    if r == "JOKER":
        return 0
    if r == "A":
        return 14 if ace_high else 1
    return {"J": 11, "Q": 12, "K": 13}.get(r, int(r) if r.isdigit() else 0)



def refill(g, p):
    while len(g["hands"].get(p, [])) < 3 and g["deck"]:
        g["hands"][p].append(g["deck"].pop(0))


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





def check_win(g, p):
    if not g["hands"].get(p) and not g["faceup"].get(p) and not g["facedown"].get(p):
        position = len(g["dead"])
        result = "win" if position == 0 else "lose"
        record_result(p, "pooheads", result, 0)
        g["players"].remove(p)
        g["dead"].append(p)
        return True
    return False

def effective_top(g):
    for c in reversed(g["pile"]):
        if get_rank(c) not in ("3", "JOKER"):
            return c
    return None


def effective_top_value(g):
    top = effective_top(g)
    if top is None:
        return None, None
    r = get_rank(top)
    if r == "A":
        ace_mode = g.get("aceMode", "high")
        v = 14 if ace_mode == "high" else 1
        return v, r
    return value(top), r


def apply_jokers(g, count):

    players = g["players"]
    n = len(players)
    if n < 2:
        return

    old_hands = {p: g["hands"].get(p, [])[:] for p in players}
    for i, p in enumerate(players):
        donor_idx = (i - count) % n
        donor = players[donor_idx]
        g["hands"][p] = old_hands[donor]


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



def valid_move(g, p, cards, from_facedown=False):
    if not cards:
        return False

    ranks = [get_rank(c) for c in cards]
    if len(set(ranks)) != 1:
        return False

    r = ranks[0]

    owned = g["hands"].get(p, []) + g["faceup"].get(p, []) + g["facedown"].get(p, [])
    if not all(c in owned for c in cards):
        return False

    top_v, top_r = effective_top_value(g)

    if r in ("2", "3", "JOKER"):
        return True
    if r == "10":
        if g.get("sevenRule"):
            return False
        return True
    if r == "8":
        if g.get("sevenRule"):
            return False
        if top_v is None:
            return True
        return top_v <= 8
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


def valid_move_with_ace(g, p, cards, ace_mode):

    r = get_rank(cards[0]) if cards else None
    if r != "A":
        return valid_move(g, p, cards)

    owned = g["hands"].get(p, []) + g["faceup"].get(p, []) + g["facedown"].get(p, [])
    if not all(c in owned for c in cards):
        return False

    top_v, top_r = effective_top_value(g)

    if g.get("sevenRule"):
        if ace_mode == "low":
            return True
        else:
            return False 

    if top_v is None:
        return True 

    ace_v = 1 if ace_mode == "low" else 14
    return ace_v >= top_v


def can_player_play(g, p):
    hand = g["hands"].get(p, [])
    faceup = g["faceup"].get(p, [])
    facedown = g["facedown"].get(p, [])

    if hand:
        candidates = hand
    elif faceup:
        candidates = faceup
    else:
        candidates = facedown

    for c in candidates:
        if valid_move(g, p, [c]):
            return True
    return False


def pickup_pile(g, user):
    g["hands"][user] = g["hands"].get(user, []) + g["pile"]
    g["pile"] = []
    g["afterTwo"] = False
    g["sevenRule"] = False
    g["aceMode"] = "high"



swap_timers = {}

def end_swap_phase(code):
    games = load_json(GAME_FILE)
    g = games["games"].get(code)
    if not g or g.get("phase") != "swap":
        return
    g["phase"] = "playing"
    g.pop("swapReady", None)
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


@socketio.on("swap")
def swap(data):
    games = load_json(GAME_FILE)
    code = data["code"]
    user = data.get("username")
    g = games["games"].get(code)

    if not g or g.get("phase") != "swap":
        return

    hand_card = data.get("handCard")
    face_card = data.get("faceCard")

    hand = g["hands"].get(user, [])
    faceup = g["faceup"].get(user, [])

    if hand_card not in hand or face_card not in faceup:
        return

    hi = hand.index(hand_card)
    fi = faceup.index(face_card)
    hand[hi], faceup[fi] = faceup[fi], hand[hi]

    g["hands"][user] = hand
    g["faceup"][user] = faceup

    save_json(GAME_FILE, games)
    socketio.emit("state", g, to=code)


@socketio.on("swapReady")
def swap_ready(data):
    games = load_json(GAME_FILE)
    code = data["code"]
    user = data.get("username")
    g = games["games"].get(code)

    if not g or g.get("phase") != "swap":
        return

    ready_set = g.setdefault("swapReady", [])
    if user not in ready_set:
        ready_set.append(user)

    save_json(GAME_FILE, games)

    if set(ready_set) >= set(g["players"]):
        if code in swap_timers:
            swap_timers[code].cancel()
            del swap_timers[code]
        g["phase"] = "playing"
        g.pop("swapReady", None)
        save_json(GAME_FILE, games)

    socketio.emit("state", g, to=code)


@socketio.on("play")
def play(data):
    games = load_json(GAME_FILE)
    code = data["code"]
    cards = data.get("cards", [])  
    user = data.get("username")
    ace_choice = data.get("aceMode", "high")

    g = games["games"][code]

    if g.get("phase") == "swap":
        return
    
    if g["turn"] != user or user not in g["players"]:
        return


    hand    = g["hands"].get(user, [])
    faceup  = g["faceup"].get(user, [])
    facedown = g["facedown"].get(user, [])

    playing_from_facedown = False
    playing_from_faceup   = False

    if hand:
        source = "hand"
    elif faceup:
        source = "faceup"
        playing_from_faceup = True
    else:
        source = "facedown"
        playing_from_facedown = True

    jokers = [c for c in cards if get_rank(c) == "JOKER"]
    non_jokers = [c for c in cards if get_rank(c) != "JOKER"]

    if jokers:
        g["pile"] += jokers
        for c in jokers:
            for k in ("hands", "faceup", "facedown"):
                if c in g[k].get(user, []):
                    g[k][user].remove(c)

        apply_jokers(g, len(jokers))

        for p in g["players"]:
            refill(g, p)

        if not check_win(g, user):
            next_player(g, user)

        save_json(GAME_FILE, games)
        socketio.emit("state", g, to=code)
        return

    cards = non_jokers

    r = get_rank(cards[0]) if cards else None

    if r == "A":
        move_ok = valid_move_with_ace(g, user, cards, ace_choice)
    else:
        move_ok = valid_move(g, user, cards, from_facedown=playing_from_facedown)

    if not move_ok:
        if playing_from_faceup or playing_from_facedown:

            for c in cards:
                if c in g[source].get(user, []):
                    g[source][user].remove(c)
            g["pile"] += cards
            pickup_pile(g, user)
            next_player(g, user)
            save_json(GAME_FILE, games)
            socketio.emit("state", g, to=code)
            socketio.emit("invalidPlay", {"msg": f"Picked up the pile."}, to=request.sid)
        else:
            socketio.emit("invalidPlay", {"msg": "You can't play that card!"}, to=request.sid)
        return

    for c in cards:
        for k in ("hands", "faceup", "facedown"):
            if c in g[k].get(user, []):
                g[k][user].remove(c)

    count = len(cards)
    extra_turn = False
    burn = False

    record_pile_history(g, cards)

    if r == "2":
        g["pile"] += cards
        g["afterTwo"] = True
        g["sevenRule"] = False
        g["aceMode"] = "high"

    elif r == "3":
        g["pile"] += cards

    elif r == "7":
        g["pile"] += cards
        g["sevenRule"] = True
        g["afterTwo"] = False
        g["aceMode"] = "high"

    elif r == "8":
        g["pile"] += cards
        g["sevenRule"] = False
        g["afterTwo"]  = False
        g["pendingSkip"] = count

    elif r == "10":
        g["pile"] += cards
        g["pile"] = []
        g["pileHistory"] = []
        g["afterTwo"] = False
        g["sevenRule"] = False
        g["aceMode"] = "high"
        burn = True
        extra_turn = True

    elif r == "A":
        g["pile"] += cards
        g["aceMode"] = ace_choice
        g["afterTwo"] = False
        g["sevenRule"] = False
        
    else:
        g["pile"] += cards
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
    players_before_win = g["players"][:] 
    idx = players_before_win.index(user)
    next_p = players_before_win[(idx + 1) % len(players_before_win)]


    refill(g, user)
    won = check_win(g, user)
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
    
    if len(g["players"]) <= 1:
        all_players = list(g["dead"]) + g["players"]
        record_played_with_all(all_players)
    save_json(GAME_FILE, games)
    socketio.emit("state", g, to=code)


@socketio.on("pickup")
def pickup(data):
    games = load_json(GAME_FILE)
    code = data["code"]
    user = data.get("username")
    g = games["games"][code]

    if g["turn"] != user:
        return

    pickup_pile(g, user)
    next_player(g, user)
    save_json(GAME_FILE, games)
    socketio.emit("state", g, to=code)


@socketio.on("start")
def start(data):
    games = load_json(GAME_FILE)
    deck_data = load_json(CARDS_FILE)

    code = data["code"]
    g = games["games"][code]
    deck = deck_data["deck"][:]
    random.shuffle(deck)

    g.update({
        "hands": {},
        "faceup": {},
        "facedown": {},
        "deck": deck,
        "pile": [],
        "pileHistory": [],
        "afterTwo": False,
        "sevenRule": False,
        "aceMode": "high",
        "dead": [],
        "phase": "swap",
        "swapReady": []
    })

    for p in g["players"]:
        g["facedown"][p] = [deck.pop() for _ in range(3)]
        g["faceup"][p] = [deck.pop() for _ in range(3)]
        g["hands"][p] = [deck.pop() for _ in range(3)]

    g["deck"] = deck
    g["turn"] = g["players"][0]

    save_json(GAME_FILE, games)
    socketio.emit("state", g, to=code)

    if code in swap_timers:
        swap_timers[code].cancel()

    t = threading.Timer(20.0, end_swap_phase, args=[code])
    t.daemon = True
    t.start()
    swap_timers[code] = t

@socketio.on('send_global_msg')
def handle_global(data):
    if session.get("username"):
        code = data.get("code")
        emit('receive_msg', {
            'sender': session.get("username"),
            'msg': data['msg'],
            'type': 'global'
        }, to=code)


@app.route("/pooheads", methods=["GET", "POST"])
@login_required
def index():
    games = load_json(GAME_FILE)
    username = session["username"]
    if request.method == "POST":

        if "create" in request.form:
            code = str(random.randint(100000, 999999))

            games.setdefault("games", {})[code] = {
                "players": [],
                "deck": [],
                "pile": [],
                "pileHistory": [],
                "turn": None,
                "afterTwo": False,
                "sevenRule": False,
                "aceMode": "high",
                "dead": [],
                "phase": "lobby"
            }

            save_json(GAME_FILE, games)
            return redirect(url_for("game", code=code))

        if "join" in request.form:
            code = request.form.get("room_code")
            if code in games.get("games", {}):
                room = games["games"][code]

                if username in room["players"]:
                    return render_template("/pooheads/index.html", error=f'The name "{username}" is already taken in room {code}.', username=username)

                if len(room["players"]) >= MAX_PLAYERS:
                    return render_template("/pooheads/index.html", error="That room is full (max 5 players).", username=username)
 
                room["players"].append(username)
                save_json(GAME_FILE, games)
                return redirect(url_for("game", code=code))

    return render_template("/pooheads/index.html", username=username)


@app.route("/pooheads/game")
@login_required
def game():
    code = request.args.get("code")
    username = session.get("username")

    if not code or not username:
        return redirect(url_for("/pooheads"))

    return render_template(
        "/pooheads/game.html",
        roomCode=code,
        username=username
    )

