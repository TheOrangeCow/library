from flask import Blueprint, request, session, render_template, redirect, url_for
from flask_socketio import join_room, emit
from auth.auth import get_chips, update_chips, get_theme
from functools import wraps
import json, os, random, threading
from auth.auth import record_result
from auth.auth import record_result, record_played_with_all, is_plus

from core import app, socketio

whitejack_bp = Blueprint(
    'whitejack', 
    __name__,
    template_folder='templates',
    static_folder='static',
    static_url_path='/whitejack/static'
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
GAME_FILE = os.path.join(BASE_DIR, "game.json")
MAX_PLAYERS = 6
file_lock = threading.RLock()

SUITS = ["H", "D", "C", "S"]
RANKS = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]

DEALER_STAND_THRESHOLD = 4


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
        return 1
    return int(r)


def base_total(hand):
    if len(hand) < 2:
        return sum(card_value(c) for c in hand)
    return card_value(hand[0]) - card_value(hand[1])


def is_white_jack(hand):
    return len(hand) == 2 and base_total(hand) == 0


def is_bust(running_total):
    return running_total < 0


def dealer_should_hit(running_total):
    return running_total > DEALER_STAND_THRESHOLD


def resolve_player(player_total, player_busted, dealer_total, dealer_busted):
    if player_busted:
        return "bust"
    if dealer_busted:
        return "win"
    if player_total < dealer_total:
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


@socketio.on("wj_join")
def wj_join(data):
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
        g["running_total"][user] = 0
        g["swaps_used"][user] = 0
        g["status"][user] = "waiting"
    save_json(GAME_FILE, games)
    join_room(code)
    socketio.emit("wj_state", get_state_for(g, user), to=code)


@socketio.on("wj_bet")
def wj_bet(data):
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
        socketio.emit("wj_error", {"msg": "Invalid bet amount."}, to=request.sid)
        return
    g["bets"][user] = amount
    g["chips"][user] = chips - amount
    g["status"][user] = "bet_placed"
    save_json(GAME_FILE, games)
    if all(g["status"].get(p) == "bet_placed" for p in g["players"]):
        deal_round(code, games)
    else:
        for p in g["players"]:
            socketio.emit("wj_state", get_state_for(g, p), to=code)


def deal_round(code, games):
    g = games["games"][code]
    deck = g["deck"]
    for p in g["players"]:
        c1, c2 = deck.pop(), deck.pop()
        if card_value(c1) < card_value(c2):
            c1, c2 = c2, c1
        g["hands"][p] = [c1, c2]
        g["running_total"][p] = card_value(c1) - card_value(c2)
        g["swaps_used"][p] = 0
        if is_white_jack(g["hands"][p]):
            g["status"][p] = "whitejack"
        else:
            g["status"][p] = "playing"
    g["dealer_hand"] = [deck.pop(), deck.pop()]
    g["phase"] = "playing"
    g["current_player_idx"] = 0
    g["turn"] = g["players"][0]
    g["doubled"] = {p: False for p in g["players"]}

    save_json(GAME_FILE, games)
    for p in g["players"]:
        socketio.emit("wj_state", get_state_for(g, p), to=code)

    advance_if_done(code)


@socketio.on("wj_swap")
def wj_swap(data):
    code = data["code"]
    user = data["username"]
    card_idx = data.get("index")
    games = load_json(GAME_FILE)
    g = games["games"].get(code)
    if not g or g.get("phase") != "swap":
        return
    if g.get("turn") != user:
        return
    if card_idx not in (0, 1):
        return
    if g["swaps_used"].get(user, 0) >= 1:
        socketio.emit("wj_error", {"msg": "You've already used your swap."}, to=request.sid)
        return
    hand = g["hands"][user]
    old_card = hand[card_idx]
    new_card = g["deck"].pop()
    hand[card_idx] = new_card
    g["deck"].insert(0, old_card)
    g["swaps_used"][user] = g["swaps_used"].get(user, 0) + 1
    save_json(GAME_FILE, games)
    for p in g["players"]:
        socketio.emit("wj_state", get_state_for(g, p), to=code)


@socketio.on("wj_lock")
def wj_lock(data):
    code = data["code"]
    user = data["username"]
    games = load_json(GAME_FILE)
    g = games["games"].get(code)
    if not g or g.get("phase") != "swap":
        return
    if g.get("turn") != user:
        return
    hand = g["hands"][user]
    total = base_total(hand)
    g["running_total"][user] = total
    if is_white_jack(hand):
        g["status"][user] = "whitejack"
    else:
        g["status"][user] = "playing"
    save_json(GAME_FILE, games)
    for p in g["players"]:
        socketio.emit("wj_state", get_state_for(g, p), to=code)
    advance_swap_or_play(code)


def advance_swap_or_play(code):
    games = load_json(GAME_FILE)
    g = games["games"].get(code)
    if not g:
        return
    players = g["players"]
    cur_idx = g.get("current_player_idx", 0)
    next_idx = cur_idx + 1
    if next_idx >= len(players):
        g["phase"] = "playing"
        g["current_player_idx"] = 0
        g["turn"] = players[0]
        save_json(GAME_FILE, games)
        for p in players:
            socketio.emit("wj_state", get_state_for(g, p), to=code)
        advance_if_done(code)
    else:
        g["current_player_idx"] = next_idx
        g["turn"] = players[next_idx]
        save_json(GAME_FILE, games)
        for p in players:
            socketio.emit("wj_state", get_state_for(g, p), to=code)


def advance_if_done(code):
    games = load_json(GAME_FILE)
    g = games["games"].get(code)
    if not g:
        return
    player = g.get("turn")
    if not player:
        run_dealer(code)
        return
    status = g["status"].get(player)
    if status in ("whitejack", "bust", "stand"):
        save_json(GAME_FILE, games)
        next_player_turn(code)
    else:
        save_json(GAME_FILE, games)
        for p in g["players"]:
            socketio.emit("wj_state", get_state_for(g, p), to=code)


@socketio.on("wj_hit")
def wj_hit(data):
    code = data["code"]
    user = data["username"]
    games = load_json(GAME_FILE)
    g = games["games"].get(code)
    if not g or g.get("phase") != "playing":
        return
    if g.get("turn") != user:
        return
    if g["status"].get(user) != "playing":
        return
    card = g["deck"].pop()
    g["hands"][user].append(card)
    g["running_total"][user] -= card_value(card)
    rt = g["running_total"][user]
    if rt == 0:
        g["status"][user] = "whitejack" if len(g["hands"][user]) == 2 else "stand"
        if len(g["hands"][user]) > 2:
            g["status"][user] = "perfect"
    elif is_bust(rt):
        g["status"][user] = "bust"
    save_json(GAME_FILE, games)
    for p in g["players"]:
        socketio.emit("wj_state", get_state_for(g, p), to=code)
    if g["status"].get(user) in ("bust", "perfect", "whitejack"):
        next_player_turn(code)


@socketio.on("wj_stand")
def wj_stand(data):
    code = data["code"]
    user = data["username"]
    games = load_json(GAME_FILE)
    g = games["games"].get(code)
    if not g or g.get("phase") != "playing":
        return
    if g.get("turn") != user:
        return
    if g["status"].get(user) != "playing":
        return
    g["status"][user] = "stand"
    save_json(GAME_FILE, games)
    for p in g["players"]:
        socketio.emit("wj_state", get_state_for(g, p), to=code)
    next_player_turn(code)


@socketio.on("wj_double")
def wj_double(data):
    code = data["code"]
    user = data["username"]
    games = load_json(GAME_FILE)
    g = games["games"].get(code)
    if not g or g.get("phase") != "playing":
        return
    if g.get("turn") != user:
        return
    if len(g["hands"][user]) != 2:
        socketio.emit("wj_error", {"msg": "Can only double right after locking in."}, to=request.sid)
        return
    bet = g["bets"][user]
    if g["chips"][user] < bet:
        socketio.emit("wj_error", {"msg": "Not enough chips to double down."}, to=request.sid)
        return
    g["chips"][user] -= bet
    g["bets"][user] = bet * 2
    g["doubled"][user] = True
    card = g["deck"].pop()
    g["hands"][user].append(card)
    g["running_total"][user] -= card_value(card)
    rt = g["running_total"][user]
    if rt == 0:
        g["status"][user] = "perfect"
    elif is_bust(rt):
        g["status"][user] = "bust"
    else:
        g["status"][user] = "stand"
    save_json(GAME_FILE, games)
    for p in g["players"]:
        socketio.emit("wj_state", get_state_for(g, p), to=code)
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
            socketio.emit("wj_state", get_state_for(g, p), to=code)
        advance_if_done(code)


def run_dealer(code):
    games = load_json(GAME_FILE)
    g = games["games"].get(code)
    if not g:
        return
    g["phase"] = "dealer"
    dealer_total = base_total(g["dealer_hand"])
    dealer_white_jack = is_white_jack(g["dealer_hand"])
    dealer_busted = is_bust(dealer_total)
    if not dealer_white_jack and not dealer_busted:
        while dealer_should_hit(dealer_total):
            card = g["deck"].pop()
            g["dealer_hand"].append(card)
            dealer_total -= card_value(card)
            if is_bust(dealer_total):
                dealer_busted = True
                break

    results = {}
    for p in g["players"]:
        hand = g["hands"].get(p, [])
        player_total = g["running_total"].get(p, base_total(hand))
        player_busted = g["status"].get(p) == "bust"
        bet = g["bets"].get(p, 0)
        if g["status"].get(p) == "whitejack" and not dealer_white_jack:
            winnings = int(bet * 2.5)
            g["chips"][p] = g["chips"].get(p, 0) + winnings
            results[p] = {"result": "whitejack", "winnings": winnings, "total": player_total}
        else:
            outcome = resolve_player(player_total, player_busted, dealer_total, dealer_busted)
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
    g["dealer_busted"] = dealer_busted
    g["phase"] = "done"
    save_json(GAME_FILE, games)
    for p in g["players"]:
        current_account = get_chips(p)
        delta = g["chips"][p] - current_account
        update_chips(p, delta)
    for p in g["players"]:
        r = results[p]
        delta = r["winnings"] - g["bets"].get(p, 0)
        record_result(p, "whitejack", r["result"], delta)

    record_played_with_all(g["players"])
    socketio.emit("wj_state", g, to=code)


@socketio.on("wj_new_round")
def wj_new_round(data):
    code = data["code"]
    games = load_json(GAME_FILE)
    g = games["games"].get(code)
    if not g:
        return
    if g.get("phase") in ("dealer", "done"):
        return
    g["players"] = [p for p in g["players"] if g["chips"].get(p, 0) > 0]
    for p in g["players"]:
        g["bets"][p] = 0
        g["hands"][p] = []
        g["running_total"][p] = 0
        g["swaps_used"][p] = 0
        g["status"][p] = "waiting"
    g["dealer_hand"] = []
    g["results"] = {}
    g["phase"] = "betting"
    g["turn"] = None
    if len(g["deck"]) < 52:
        g["deck"] = make_deck(6)
    save_json(GAME_FILE, games)
    socketio.emit("wj_state", g, to=code)


@socketio.on('white_game_msg')
def handle_white_msg(data):
    if session.get("username"):
        code = data.get("code")
        emit('white_receive_msg', {
            'sender': session.get("username"),
            'msg': data['msg'],
        }, to=code)


@whitejack_bp.route("/whitejack/rooms")
@login_required
def public_rooms():
    username = session["username"]
    if not is_plus(username):
        return redirect("https://library.theorangecow.org/plus?upgrade=true")
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


@whitejack_bp.route("/whitejack", methods=["GET", "POST"])
@login_required
def index():
    username = session["username"]
    if not is_plus(username):
        return redirect("https://library.theorangecow.org/plus?upgrade=true")
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
                "running_total": {},
                "swaps_used": {},
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
            return redirect(url_for("whitejack.game", theme=get_theme(username), code=code))

        if "join" in request.form:
            code = request.form.get("room_code", "").strip()
            if code in games.get("games", {}):
                room = games["games"][code]
                if len(room["players"]) >= MAX_PLAYERS:
                    return render_template("whitejack/index.html",
                        error="Room is full.", username=username)
                return redirect(url_for("whitejack.game", theme=get_theme(username), code=code))
            else:
                return render_template("whitejack/index.html",
                    error="Room not found.", theme=get_theme(username), username=username)

    return render_template("whitejack/index.html", theme=get_theme(username), username=username)


@whitejack_bp.route("/whitejack/game")
@login_required
def game():
    code = request.args.get("code")
    username = session["username"]
    if not is_plus(username):
        return redirect("https://library.theorangecow.org/plus?upgrade=true")
    if not code:
        return redirect(url_for("whitejack.index"))
    return render_template("whitejack/game.html", theme=get_theme(username), roomCode=code, username=username)