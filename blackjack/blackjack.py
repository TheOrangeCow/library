from flask import Blueprint, request, session, render_template, redirect, url_for
from flask_socketio import join_room
from auth.auth import get_chips, update_chips, get_theme
from functools import wraps
import json, os, random, threading
from auth.auth import record_result
from auth.auth import record_result, record_played_with_all

from core import app, socketio

blackjack_bp = Blueprint(
    'blackjack', __name__,
    template_folder='templates',
    static_folder='static',
    static_url_path='/blackjack/static'
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
GAME_FILE = os.path.join(BASE_DIR, "game.json")
MAX_PLAYERS = 6
file_lock = threading.RLock()

SUITS = ["H", "D", "C", "S"]
RANKS = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]

def login_required(f):
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

def make_deck(num_decks=6):
    deck = [r + s for s in SUITS for r in RANKS] * num_decks
    random.shuffle(deck)
    return deck

def card_value(card):
    r = card[:-1]
    if r in ("J", "Q", "K"):
        return 10
    if r == "A":
        return 11
    return int(r)

def hand_total(hand):
    total = 0
    aces = 0
    for card in hand:
        v = card_value(card)
        total += v
        if card[:-1] == "A":
            aces += 1
    while total > 21 and aces:
        total -= 10
        aces -= 1
    return total

def is_bust(hand):
    return hand_total(hand) > 21

def is_blackjack(hand):
    return len(hand) == 2 and hand_total(hand) == 21

def dealer_should_hit(hand):
    total = hand_total(hand)
    if total < 17:
        return True
    if total == 17:
        aces = sum(1 for c in hand if c[:-1] == "A")
        raw = sum(card_value(c) for c in hand)
        if aces and raw > 21:
            return True
    return False

def resolve_player(player_total, dealer_total, dealer_bust):
    if player_total > 21:
        return "bust"
    if dealer_bust:
        return "win"
    if player_total > dealer_total:
        return "win"
    if player_total == dealer_total:
        return "push"
    return "lose"

def get_state_for(g, username):
    import copy
    s = copy.deepcopy(g)
    if g.get("phase") == "playing":
        if s.get("dealer_hand") and len(s["dealer_hand"]) >= 2:
            s["dealer_hand_visible"] = [s["dealer_hand"][0], "back"]
        else:
            s["dealer_hand_visible"] = s.get("dealer_hand", [])
    else:
        s["dealer_hand_visible"] = s.get("dealer_hand", [])
    return s


@socketio.on("bj_join")
def bj_join(data):
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
        g["chips"][user] = get_chips(user)
        g["bets"][user] = 0
        g["hands"][user] = []
        g["status"][user] = "waiting"
    save_json(GAME_FILE, games)
    join_room(code)
    socketio.emit("bj_state", get_state_for(g, user), to=code)


@socketio.on("bj_bet")
def bj_bet(data):
    code = data["code"]
    user = data["username"]
    amount = int(data.get("amount", 0))
    games = load_json(GAME_FILE)
    g = games["games"].get(code)
    if not g or g.get("phase") != "betting":
        return
    if user not in g["players"]:
        return
    chips = g["chips"].get(user, 0)
    if amount < 1 or amount > chips:
        socketio.emit("bj_error", {"msg": "Invalid bet amount."}, to=request.sid)
        return
    g["bets"][user] = amount
    g["chips"][user] = chips - amount
    g["status"][user] = "bet_placed"
    save_json(GAME_FILE, games)
    if all(g["status"].get(p) == "bet_placed" for p in g["players"]):
        deal_round(code, games)
    else:
        for p in g["players"]:
            socketio.emit("bj_state", get_state_for(g, p), to=code)


def deal_round(code, games):
    g = games["games"][code]
    deck = g["deck"]
    for p in g["players"]:
        g["hands"][p] = [deck.pop(), deck.pop()]
        g["status"][p] = "playing"
    g["dealer_hand"] = [deck.pop(), deck.pop()]
    g["phase"] = "playing"
    g["current_player_idx"] = 0
    g["turn"] = g["players"][0]
    g["doubled"] = {p: False for p in g["players"]}
    g["split_hands"] = {}

    save_json(GAME_FILE, games)
    for p in g["players"]:
        socketio.emit("bj_state", get_state_for(g, p), to=code)

    advance_if_done(code)


def advance_if_done(code):
    games = load_json(GAME_FILE)
    g = games["games"].get(code)
    if not g:
        return
    player = g.get("turn")
    if not player:
        run_dealer(code)
        return
    hand = g["hands"].get(player, [])
    if is_blackjack(hand) or is_bust(hand):
        g["status"][player] = "blackjack" if is_blackjack(hand) else "bust"
        save_json(GAME_FILE, games)
        next_player_turn(code)
    else:
        save_json(GAME_FILE, games)
        for p in g["players"]:
            socketio.emit("bj_state", get_state_for(g, p), to=code)


@socketio.on("bj_hit")
def bj_hit(data):
    code = data["code"]
    user = data["username"]
    games = load_json(GAME_FILE)
    g = games["games"].get(code)
    if not g or g.get("phase") != "playing":
        return
    if g.get("turn") != user:
        return
    card = g["deck"].pop()
    g["hands"][user].append(card)
    if is_bust(g["hands"][user]):
        g["status"][user] = "bust"
        save_json(GAME_FILE, games)
        for p in g["players"]:
            socketio.emit("bj_state", get_state_for(g, p), to=code)
        next_player_turn(code)
    else:
        save_json(GAME_FILE, games)
        for p in g["players"]:
            socketio.emit("bj_state", get_state_for(g, p), to=code)


@socketio.on("bj_stand")
def bj_stand(data):
    code = data["code"]
    user = data["username"]
    games = load_json(GAME_FILE)
    g = games["games"].get(code)
    if not g or g.get("phase") != "playing":
        return
    if g.get("turn") != user:
        return
    g["status"][user] = "stand"
    save_json(GAME_FILE, games)
    for p in g["players"]:
        socketio.emit("bj_state", get_state_for(g, p), to=code)
    next_player_turn(code)


@socketio.on("bj_double")
def bj_double(data):
    code = data["code"]
    user = data["username"]
    games = load_json(GAME_FILE)
    g = games["games"].get(code)
    if not g or g.get("phase") != "playing":
        return
    if g.get("turn") != user:
        return
    if len(g["hands"][user]) != 2:
        socketio.emit("bj_error", {"msg": "Can only double on first two cards."}, to=request.sid)
        return
    bet = g["bets"][user]
    if g["chips"][user] < bet:
        socketio.emit("bj_error", {"msg": "Not enough chips to double down."}, to=request.sid)
        return
    g["chips"][user] -= bet
    g["bets"][user] = bet * 2
    g["doubled"][user] = True
    card = g["deck"].pop()
    g["hands"][user].append(card)
    g["status"][user] = "bust" if is_bust(g["hands"][user]) else "stand"
    save_json(GAME_FILE, games)
    for p in g["players"]:
        socketio.emit("bj_state", get_state_for(g, p), to=code)
    next_player_turn(code)


def next_player_turn(code):
    games = load_json(GAME_FILE)
    g = games["games"].get(code)
    if not g:
        return
    players = g["players"]
    cur_idx = g.get("current_player_idx", 0)
    next_idx = cur_idx + 1
    if next_idx >= len(players):
        g["turn"] = None
        save_json(GAME_FILE, games)
        run_dealer(code)
    else:
        g["current_player_idx"] = next_idx
        g["turn"] = players[next_idx]
        save_json(GAME_FILE, games)
        for p in players:
            socketio.emit("bj_state", get_state_for(g, p), to=code)
        advance_if_done(code)


def run_dealer(code):
    games = load_json(GAME_FILE)
    g = games["games"].get(code)
    if not g:
        return
    g["phase"] = "dealer"
    while dealer_should_hit(g["dealer_hand"]):
        g["dealer_hand"].append(g["deck"].pop())
    dealer_total = hand_total(g["dealer_hand"])
    dealer_bust = is_bust(g["dealer_hand"])
    results = {}
    for p in g["players"]:
        hand = g["hands"].get(p, [])
        player_total = hand_total(hand)
        bet = g["bets"].get(p, 0)
        if g["status"].get(p) == "blackjack" and not is_blackjack(g["dealer_hand"]):
            winnings = int(bet * 2.5)
            g["chips"][p] = g["chips"].get(p, 0) + winnings
            results[p] = {"result": "blackjack", "winnings": winnings, "total": player_total}
        else:
            outcome = resolve_player(player_total, dealer_total, dealer_bust)
            if outcome == "win":
                winnings = bet * 2
                g["chips"][p] = g["chips"].get(p, 0) + winnings
            elif outcome == "push":
                g["chips"][p] = g["chips"].get(p, 0) + bet
                winnings = bet
            else:
                winnings = 0
            results[p] = {"result": outcome, "winnings": winnings, "total": player_total}
    g["results"] = results
    g["dealer_total"] = dealer_total
    g["phase"] = "done"
    save_json(GAME_FILE, games)
    for p in g["players"]:
        current_account = get_chips(p)
        delta = g["chips"][p] - current_account
        update_chips(p, delta)
    for p in g["players"]:
        r = results[p]
        delta = r["winnings"] - g["bets"].get(p, 0)
        record_result(p, "blackjack", r["result"], delta)

    record_played_with_all(g["players"])
    socketio.emit("bj_state", g, to=code)


@socketio.on("bj_new_round")
def bj_new_round(data):
    code = data["code"]
    games = load_json(GAME_FILE)
    g = games["games"].get(code)
    if not g:
        return
    g["players"] = [p for p in g["players"] if g["chips"].get(p, 0) > 0]
    for p in g["players"]:
        g["bets"][p] = 0
        g["hands"][p] = []
        g["status"][p] = "waiting"
    g["dealer_hand"] = []
    g["results"] = {}
    g["phase"] = "betting"
    g["turn"] = None
    if len(g["deck"]) < 52:
        g["deck"] = make_deck(6)
    save_json(GAME_FILE, games)
    socketio.emit("bj_state", g, to=code)


@socketio.on('black_game_msg')
def handle_enraged_msg(data):
    if session.get("username"):
        code = data.get("code")
        emit('black_receive_msg', {
            'sender': session.get("username"),
            'msg': data['msg'],
        }, to=code)
        

@blackjack_bp.route("/blackjack/rooms")
@login_required
def public_rooms():
    games = load_json(GAME_FILE)
    rooms = []
    for code, g in games.get("games", {}).items():
        if g.get("public") and g.get("phase") == "betting" and len(g["players"]) < MAX_PLAYERS:
            rooms.append({
                "code": code,
                "players": len(g["players"]),
                "max": MAX_PLAYERS,
                "names": g["players"]
            })
    return {"rooms": rooms}

@blackjack_bp.route("/blackjack", methods=["GET", "POST"])
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
                "hands": {},
                "chips": {},
                "bets": {},
                "status": {},
                "dealer_hand": [],
                "deck": make_deck(6),
                "phase": "betting",
                "turn": None,
                "results": {},
                "doubled": {},
                "current_player_idx": 0,
                "public": is_public,
            }
            save_json(GAME_FILE, games)
            return redirect(url_for("blackjack.game", theme=get_theme(username), code=code))

        if "join" in request.form:
            code = request.form.get("room_code", "").strip()
            if code in games.get("games", {}):
                room = games["games"][code]
                if len(room["players"]) >= MAX_PLAYERS:
                    return render_template("blackjack/index.html",
                        error="Room is full.", username=username)
                return redirect(url_for("blackjack.game", theme=get_theme(username), code=code))
            else:
                return render_template("blackjack/index.html",
                    error="Room not found.", theme=get_theme(username), username=username)

    return render_template("blackjack/index.html", theme=get_theme(username), username=username)


@blackjack_bp.route("/blackjack/game")
@login_required
def game():
    code = request.args.get("code")
    username = session["username"]
    if not code:
        return redirect(url_for("blackjack.index"))
    return render_template("blackjack/game.html", theme=get_theme(username), roomCode=code, username=username)