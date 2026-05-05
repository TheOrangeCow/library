from flask import Blueprint, request, session, render_template, redirect, url_for
from flask_socketio import emit, join_room
from functools import wraps
from auth.auth import get_chips, update_chips, record_result
from core import app, socketio
import os, json, random, threading
from flask import request as flask_request

poker_bp = Blueprint(
    'poker', __name__,
    template_folder='templates',
    static_folder='static',
    static_url_path='/poker/static'
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
GAME_FILE = os.path.join(BASE_DIR, "game.json")

file_lock = threading.RLock()

def load_json(p):
    with file_lock:
        if not os.path.exists(p): return {}
        try:
            with open(p) as f:
                content = f.read()
                return json.loads(content) if content.strip() else {}
        except json.JSONDecodeError:
            return {}

def save_json(p, d):
    with file_lock:
        with open(p, "w") as f:
            json.dump(d, f, indent=4)

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "username" not in session:
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return decorated


SUITS = ["S", "H", "D", "C"]
RANKS = ["2","3","4","5","6","7","8","9","10","J","Q","K","A"]

def make_deck():
    return [r + s for s in SUITS for r in RANKS]

def rank_val(r):
    return {"2":2,"3":3,"4":4,"5":5,"6":6,"7":7,"8":8,"9":9,"10":10,
            "J":11,"Q":12,"K":13,"A":14}[r]

def card_rank(c):
    return c[:-1]

def card_suit(c):
    return c[-1]


from itertools import combinations

def best_hand(hole, board):
    all7 = hole + board
    best = None
    for combo in combinations(all7, 5):
        score = evaluate5(list(combo))
        if best is None or score > best:
            best = score
    return best

def evaluate5(cards):
    ranks = sorted([rank_val(card_rank(c)) for c in cards], reverse=True)
    suits = [card_suit(c) for c in cards]
    flush = len(set(suits)) == 1
    straight = (ranks == list(range(ranks[0], ranks[0]-5, -1))) or ranks == [14,5,4,3,2]
    if straight and ranks[0] == 5: ranks = [5,4,3,2,1]

    from collections import Counter
    counts = Counter(ranks)
    groups = sorted(counts.items(), key=lambda x: (x[1], x[0]), reverse=True)
    freq = [g[1] for g in groups]
    vals = [g[0] for g in groups]

    if flush and straight:   return (8, ranks)
    if freq[0] == 4:         return (7, vals)
    if freq[:2] == [3,2]:    return (6, vals)
    if flush:                return (5, ranks)
    if straight:             return (4, ranks)
    if freq[0] == 3:         return (3, vals)
    if freq[:2] == [2,2]:    return (2, vals)
    if freq[0] == 2:         return (1, vals)
    return (0, ranks)

HAND_NAMES = {8:"Royal/Straight Flush",7:"Four of a Kind",6:"Full House",
              5:"Flush",4:"Straight",3:"Three of a Kind",2:"Two Pair",
              1:"One Pair",0:"High Card"}


BLIND_LEVELS = {
    "low":  {"small": 10,  "big": 20,  "min_buy": 200,  "max_buy": 1000},
    "mid":  {"small": 50,  "big": 100, "min_buy": 1000, "max_buy": 5000},
    "high": {"small": 250, "big": 500, "min_buy": 5000, "max_buy": 25000},
}

def new_room(stake, host):
    return {
        "host": host,
        "stake": stake,
        "phase": "lobby",
        "players": [],
        "stacks": {},    
        "buy_ins": {},
        "hole_cards": {},
        "board": [],
        "deck": [],
        "pot": 0,
        "side_pots": [],
        "bets": {},
        "folded": [],
        "all_in": [],
        "dealer": 0,
        "action_on": None,
        "last_raise": 0,
        "min_raise": 0,
        "round_done": [],
    }

def serialise(g):
    c = json.loads(json.dumps(g, default=list))
    return c

def active_players(g):
    return [p for p in g["players"] if p not in g["folded"] and p not in g["all_in"]]

def next_actor(g, current):
    players = g["players"]
    n = len(players)
    idx = players.index(current)
    for i in range(1, n+1):
        cand = players[(idx+i) % n]
        if cand not in g["folded"] and cand not in g["all_in"]:
            return cand
    return None

def deal_street(g):
    if g["phase"] == "preflop":
        g["board"] = [g["deck"].pop(), g["deck"].pop(), g["deck"].pop()]
        g["phase"] = "flop"
    elif g["phase"] == "flop":
        g["board"].append(g["deck"].pop())
        g["phase"] = "turn"
    elif g["phase"] == "turn":
        g["board"].append(g["deck"].pop())
        g["phase"] = "river"
    elif g["phase"] == "river":
        g["phase"] = "showdown"

def start_betting_round(g):
    g["bets"] = {p: 0 for p in g["players"] if p not in g["folded"]}
    g["round_done"] = []
    g["last_raise"] = 0
    blind = BLIND_LEVELS[g["stake"]]
    g["min_raise"] = blind["big"]

    players = g["players"]
    n = len(players)
    dealer = g["dealer"]

    if g["phase"] == "preflop":
        sb_idx = (dealer + 1) % n
        bb_idx = (dealer + 2) % n
        action_idx = (dealer + 3) % n

        sb = players[sb_idx]
        bb = players[bb_idx]
        sb_amt = min(blind["small"], g["stacks"].get(sb, 0))
        bb_amt = min(blind["big"],   g["stacks"].get(bb, 0))

        g["stacks"][sb] = g["stacks"].get(sb, 0) - sb_amt
        g["stacks"][bb] = g["stacks"].get(bb, 0) - bb_amt
        g["pot"] += sb_amt + bb_amt
        g["bets"][sb] = sb_amt
        g["bets"][bb] = bb_amt
        g["last_raise"] = bb_amt
        g["min_raise"]  = bb_amt

        if g["stacks"].get(sb, 0) == 0: g["all_in"].add(sb)
        if g["stacks"].get(bb, 0) == 0: g["all_in"].add(bb)

        act = players[action_idx % n]
        while act in g["all_in"] and act != players[bb_idx]:
            action_idx += 1
            act = players[action_idx % n]
        g["action_on"] = act
    else:
        for i in range(1, n+1):
            cand = players[(dealer+i) % n]
            if cand not in g["folded"] and cand not in g["all_in"]:
                g["action_on"] = cand
                break

def resolve_hand(g, code):
    players = [p for p in g["players"] if p not in g["folded"]]
    if len(players) == 1:
        winner = players[0]
        winnings = g["pot"]
        g["stacks"][winner] = g["stacks"].get(winner, 0) + winnings
        g["last_result"] = {winner: {"won": winnings, "hand": "Last player standing"}}
        g["pot"] = 0
        return

    scored = {}
    for p in players:
        hole = g["hole_cards"].get(p, [])
        score = best_hand(hole, g["board"])
        scored[p] = score

    best_score = max(scored.values())
    winners = [p for p, s in scored.items() if s == best_score]

    share = g["pot"] // len(winners)
    remainder = g["pot"] % len(winners)

    g["last_result"] = {}
    for p in g["players"]:
        hand_name = HAND_NAMES.get(scored.get(p, (0,[]))[0], "") if p not in g["folded"] else ""
        won = 0
        if p in winners:
            won = share
        g["stacks"][p] = g["stacks"].get(p, 0) + won
        g["last_result"][p] = {
            "won": won,
            "hand": hand_name,
            "cards": g["hole_cards"].get(p, []) if p not in g["folded"] else [],
            "folded": p in g["folded"],
        }

    if remainder and winners:
        g["stacks"][winners[0]] += remainder

    g["pot"] = 0

def cash_out_and_record(g, code):
    buy_ins = g.get("buy_ins", {})
    for p in g["players"]:
        stack = g["stacks"].get(p, 0)
        bought = buy_ins.get(p, 0)
        delta = stack - bought
        if delta != 0:
            update_chips(p, delta)
        result = "win" if delta > 0 else "lose"
        record_result(p, "poker", result, delta)

def advance_phase(g, code):
    active = [p for p in g["players"] if p not in g["folded"]]
    if len(active) == 1:
        resolve_hand(g, code)
        g["phase"] = "showdown"
        return

    if g["phase"] == "river":
        g["phase"] = "showdown"
        resolve_hand(g, code)
    else:
        deal_street(g)
        start_betting_round(g)

def betting_complete(g):
    active = [p for p in g["players"] if p not in g["folded"] and p not in g["all_in"]]
    if not active:
        return True
    max_bet = max(g["bets"].values()) if g["bets"] else 0
    for p in active:
        if p not in g["round_done"]:
            return False
        if g["bets"].get(p, 0) < max_bet:
            return False
    return True


@poker_bp.route("/poker", methods=["GET","POST"])
@login_required
def index():
    username = session["username"]
    chips = get_chips(username)
    games = load_json(GAME_FILE)
    rooms = games.get("games", {})

    error = None

    if request.method == "POST":
        action = request.form.get("action")

        if action == "create":
            stake = request.form.get("stake", "low")
            if stake not in BLIND_LEVELS:
                stake = "low"
            code = str(random.randint(100000, 999999))
            games.setdefault("games", {})[code] = new_room(stake, username)
            save_json(GAME_FILE, games)
            return redirect(url_for("poker.game", code=code))

        if action == "join":
            code = request.form.get("code", "").strip()
            if code not in rooms:
                error = "Room not found."
            else:
                g = rooms[code]
                if username in g["players"]:
                    return redirect(url_for("poker.game", code=code))
                if len(g["players"]) >= 9:
                    error = "Room is full."
                elif g["phase"] != "lobby":
                    error = "Game already in progress."
                else:
                    save_json(GAME_FILE, games)
                    return redirect(url_for("poker.game", code=code))

    lobby_rooms = []
    for code, g in rooms.items():
        if g["phase"] == "lobby":
            lobby_rooms.append({
                "code": code,
                "stake": g["stake"],
                "host": g["host"],
                "players": len(g["players"]),
                "blinds": f'{BLIND_LEVELS[g["stake"]]["small"]}/{BLIND_LEVELS[g["stake"]]["big"]}',
                "min_buy": BLIND_LEVELS[g["stake"]]["min_buy"],
            })

    return render_template("poker/index.html",
        username=username, chips=chips,
        rooms=lobby_rooms, error=error,
        blind_levels=BLIND_LEVELS,
    )

@poker_bp.route("/poker/game")
@login_required
def game():
    code = request.args.get("code")
    username = session.get("username")
    if not code or not username:
        return redirect(url_for("poker.index"))
    games = load_json(GAME_FILE)
    if code not in games.get("games", {}):
        return redirect(url_for("poker.index"))
    return render_template("poker/game.html",
        roomCode=code, username=username,
        chips=get_chips(username),
    )


def emit_state(g, code):
    pub = serialise(g)
    pub.pop("hole_cards", None)
    pub.pop("deck", None)
    socketio.emit("state", pub, to=code)

    sid_map = g.get("sid_map", {})
    for p, hole in g.get("hole_cards", {}).items():
        sid = sid_map.get(p)
        if sid:
            socketio.emit("hole_cards", {"cards": hole}, to=sid)

@socketio.on("poker_join")
def poker_join(data):
    code = data["code"]
    username = data["username"]
    games = load_json(GAME_FILE)
    g = games.get("games", {}).get(code)
    if not g:
        return

    join_room(code)

    g.setdefault("sid_map", {})[username] = flask_request.sid

    if username not in g["players"] and g["phase"] == "lobby":
        g["players"].append(username)

    save_json(GAME_FILE, games)
    emit_state(g, code)

    hole = g.get("hole_cards", {}).get(username, [])
    if hole:
        emit("hole_cards", {"cards": hole})
@socketio.on("poker_buy_in")
def poker_buy_in(data):
    code = data["code"]
    username = data["username"]
    amount = int(data.get("amount", 0))
    games = load_json(GAME_FILE)
    g = games["games"].get(code)
    if not g or g["phase"] != "lobby":
        return

    level = BLIND_LEVELS[g["stake"]]
    if amount < level["min_buy"] or amount > level["max_buy"]:
        emit("poker_error", {"msg": f"Buy-in must be {level['min_buy']}–{level['max_buy']} chips."})
        return
    chips = get_chips(username)
    if amount > chips:
        emit("poker_error", {"msg": "Not enough chips."})
        return

    update_chips(username, -amount)
    g["stacks"][username] = g["stacks"].get(username, 0) + amount

    if "buy_ins" not in g:
        g["buy_ins"] = {}
    g["buy_ins"][username] = g["buy_ins"].get(username, 0) + amount

    save_json(GAME_FILE, games)
    emit_state(g, code)

@socketio.on("poker_start")
def poker_start(data):
    code = data["code"]
    username = data["username"]
    games = load_json(GAME_FILE)
    g = games["games"].get(code)
    if not g or g["phase"] != "lobby" or g["host"] != username:
        return
    if len(g["players"]) < 2:
        emit("poker_error", {"msg": "Need at least 2 players."})
        return
    no_stack = [p for p in g["players"] if g["stacks"].get(p, 0) == 0]
    if no_stack:
        emit("poker_error", {"msg": f"{', '.join(no_stack)} haven't bought in yet."})
        return

    start_new_hand(g)
    save_json(GAME_FILE, games)
    emit_state(g, code)

def start_new_hand(g):
    players = [p for p in g["players"] if g["stacks"].get(p, 0) > 0]
    if len(players) < 2:
        g["phase"] = "done"
        return

    g["players"] = players
    deck = make_deck()
    random.shuffle(deck)
    g["deck"] = deck
    g["board"] = []
    g["pot"] = 0
    g["side_pots"] = []
    g["folded"] = []
    g["all_in"] = []
    g["round_done"] = []
    g["last_result"] = {}
    g["bets"] = {}
    g["phase"] = "preflop"

    g["dealer"] = (g.get("dealer", 0) + 1) % len(players)

    g["hole_cards"] = {}
    for p in players:
        g["hole_cards"][p] = [deck.pop(), deck.pop()]

    start_betting_round(g)

@socketio.on("poker_action")
def poker_action(data):
    code = data["code"]
    username = data["username"]
    action = data["action"]
    amount = int(data.get("amount", 0))

    games = load_json(GAME_FILE)
    g = games["games"].get(code)
    if not g or g.get("action_on") != username:
        return

    max_bet = max(g["bets"].values()) if g["bets"] else 0
    stack = g["stacks"].get(username, 0)
    my_bet = g["bets"].get(username, 0)
    to_call = max_bet - my_bet

    if action == "fold":
        g["folded"].append(username)
        g["round_done"].append(username)

    elif action == "check":
        if to_call > 0:
            emit("poker_error", {"msg": "Can't check — there's a bet to call."})
            return
        g["round_done"].append(username)

    elif action == "call":
        call_amt = min(to_call, stack)
        g["stacks"][username] -= call_amt
        g["bets"][username] = my_bet + call_amt
        g["pot"] += call_amt
        if g["stacks"][username] == 0:
            g["all_in"].append(username)
        g["round_done"].append(username)

    elif action == "raise":
        min_r = g.get("min_raise", BLIND_LEVELS[g["stake"]]["big"])
        total_bet = my_bet + to_call + max(amount, min_r)
        actual_raise = min(total_bet - my_bet, stack)
        g["stacks"][username] -= actual_raise
        g["pot"] += actual_raise
        new_bet = my_bet + actual_raise
        g["bets"][username] = new_bet
        g["last_raise"] = new_bet - max_bet
        g["min_raise"] = g["last_raise"]
        if g["stacks"][username] == 0:
            g["all_in"].append(username)
        g["round_done"] = [username]

    elif action == "allin":
        g["stacks"][username] = 0
        total = my_bet + stack
        g["pot"] += stack
        g["bets"][username] = total
        if total > max_bet:
            g["last_raise"] = total - max_bet
            g["min_raise"] = g["last_raise"]
            g["round_done"] = [username]
        else:
            g["round_done"].append(username)
        g["all_in"].append(username)

    remaining_active = [p for p in g["players"]
                        if p not in g["folded"] and p not in g["all_in"]]
    if len(remaining_active) <= 1 or betting_complete(g):
        advance_phase(g, code)
        if g["phase"] == "showdown":
            cash_out_and_record(g, code)
    else:
        nxt = next_actor(g, username)
        g["action_on"] = nxt

    save_json(GAME_FILE, games)
    emit_state(g, code)

@socketio.on("poker_next_hand")
def poker_next_hand(data):
    code = data["code"]
    username = data["username"]
    games = load_json(GAME_FILE)
    g = games["games"].get(code)
    if not g or g["phase"] != "showdown" or g["host"] != username:
        return

    start_new_hand(g)
    save_json(GAME_FILE, games)
    emit_state(g, code)

@socketio.on("poker_leave")
def poker_leave(data):
    code = data["code"]
    username = data["username"]
    games = load_json(GAME_FILE)
    g = games["games"].get(code)
    if not g:
        return

    stack = g["stacks"].pop(username, 0)
    if stack > 0:
        update_chips(username, stack)

    if username in g["players"]:
        g["players"].remove(username)
    for lst in ("folded", "all_in", "round_done"):
        if username in g.get(lst, []):
            g[lst].remove(username)
    g.get("hole_cards", {}).pop(username, None)
    g.get("sid_map", {}).pop(username, None)

    if not g["players"]:
        del games["games"][code]
    else:
        if g.get("host") == username:
            g["host"] = g["players"][0]
        save_json(GAME_FILE, games)
        emit_state(g, code)
        return

    save_json(GAME_FILE, games)