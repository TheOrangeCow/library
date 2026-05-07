from flask import Blueprint, request, session, redirect, url_for, render_template
import json, os, hashlib, time, hmac
from dotenv import load_dotenv

auth_bp = Blueprint('auth', __name__, template_folder='templates')

load_dotenv()

CODE_SECRET  = os.getenv("CODE_SECRET")

USERS_FILE = os.path.join(os.path.dirname(__file__), "users.json")

def get_join_code():
    hour_bucket = int(time.time()) // 3600
    raw = hmac.new(CODE_SECRET.encode(), str(hour_bucket).encode(), hashlib.sha256).hexdigest()
    return raw[:6].upper()

def load_users():
    if not os.path.exists(USERS_FILE):
        return {"users": {}}
    with open(USERS_FILE) as f:
        return json.load(f)

def save_users(data):
    with open(USERS_FILE, "w") as f:
        json.dump(data, f, indent=4)

def hash_pw(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"].strip()
        confirm  = request.form["confirm"].strip()
        join_code = request.form.get("join_code", "").strip().upper()

        if join_code != get_join_code():
            return render_template("auth/register.html", error="Invalid or expired join code.")
        
        if password != confirm:
            return render_template("auth/register.html", error="Passwords do not match.")

        data = load_users()
        if username in data["users"]:
            return render_template("auth/register.html", error="Username already taken.")

        data["users"][username] = {
            "password": hash_pw(password),
            "chips": 1000
        }
        save_users(data)
        session["username"] = username
        return redirect(url_for("home"))
    return render_template("auth/register.html")

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"].strip()
        data = load_users()
        user = data["users"].get(username)
        if not user or user["password"] != hash_pw(password):
            return render_template("auth/login.html", error="Invalid credentials.")
        session["username"] = username
        return redirect(url_for("home"))
    return render_template("auth/login.html")

@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))

def get_chips(username):
    data = load_users()
    return data["users"].get(username, {}).get("chips", 0)

def update_chips(username, amount):
    data = load_users()
    if username in data["users"]:
        data["users"][username]["chips"] += amount
        save_users(data)

def record_result(username, game, result, chips_delta):
    data = load_users()
    user = data["users"].get(username)
    if not user:
        return
    history = user.setdefault("history", [])
    history.append({
        "game": game,
        "result": result,
        "chips_delta": chips_delta,
        "timestamp": __import__("time").time()
    })
    user["history"] = history[-50:]

    stats = user.setdefault("stats", {})
    stats["games_played"] = stats.get("games_played", 0) + 1
    if result in ("win", "blackjack"):
        stats["wins"] = stats.get("wins", 0) + 1
    if result == "blackjack":
        stats["blackjacks"] = stats.get("blackjacks", 0) + 1
    if chips_delta > stats.get("biggest_win", 0):
        stats["biggest_win"] = chips_delta
    current_chips = user.get("chips", 0)
    if current_chips > stats.get("peak_chips", 0):
        stats["peak_chips"] = current_chips

    save_users(data)
    check_achievements(username)

def record_played_with(username, other_players):
    data = load_users()
    user = data["users"].get(username)
    if not user:
        return
    recent = user.setdefault("recent_players", [])
    for p in other_players:
        if p == username:
            continue
        if p in recent:
            recent.remove(p)
        recent.insert(0, p)
    user["recent_players"] = recent[:20]
    save_users(data)


def record_played_with_all(players):
    data = load_users()
    for username in players:
        user = data["users"].get(username)
        if not user:
            continue
        others = [p for p in players if p != username]
        recent = user.setdefault("recent_players", [])
        for p in others:
            if p in recent:
                recent.remove(p)
            recent.insert(0, p)
        user["recent_players"] = recent[:20]
    save_users(data)


def check_achievements(username):
    data = load_users()
    user = data["users"].get(username)
    if not user:
        return
    stats = user.get("stats", {})
    unlocked = user.setdefault("achievements", [])

    all_achievements = [
        {
            "id": "first_win",
            "name": "First Blood",
            "desc": "Win your first game",
            "icon": "🎉",
            "check": lambda s: s.get("wins", 0) >= 1
        },
        {
            "id": "ten_wins",
            "name": "On a Roll",
            "desc": "Win 10 games",
            "icon": "🔥",
            "check": lambda s: s.get("wins", 0) >= 10
        },
        {
            "id": "fifty_wins",
            "name": "Veteran",
            "desc": "Win 50 games",
            "icon": "🏆",
            "check": lambda s: s.get("wins", 0) >= 50
        },
        {
            "id": "big_win",
            "name": "High Roller",
            "desc": "Win 500+ chips in one go",
            "icon": "💰",
            "check": lambda s: s.get("biggest_win", 0) >= 500
        },
        {
            "id": "whale",
            "name": "Whale",
            "desc": "Win 1000+ chips in one go",
            "icon": "🐋",
            "check": lambda s: s.get("biggest_win", 0) >= 1000
        },
        {
            "id": "played_10",
            "name": "Regular",
            "desc": "Play 10 games",
            "icon": "🃏",
            "check": lambda s: s.get("games_played", 0) >= 10
        },
        {
            "id": "played_50",
            "name": "Dedicated",
            "desc": "Play 50 games",
            "icon": "⭐",
            "check": lambda s: s.get("games_played", 0) >= 50
        },
        {
            "id": "rich",
            "name": "Rich",
            "desc": "Hold 2000+ chips at once",
            "icon": "💎",
            "check": lambda s: s.get("peak_chips", 0) >= 2000
        },
        {
            "id": "blackjack",
            "name": "Natural",
            "desc": "Hit a Blackjack",
            "icon": "🃏",
            "check": lambda s: s.get("blackjacks", 0) >= 1
        },
        {
            "id": "blackjack5",
            "name": "Card Sharp",
            "desc": "Hit 5 Blackjacks",
            "icon": "🎰",
            "check": lambda s: s.get("blackjacks", 0) >= 5
        },
    ]

    newly_unlocked = []
    for a in all_achievements:
        if a["id"] not in unlocked and a["check"](stats):
            unlocked.append(a["id"])
            newly_unlocked.append(a)

    user["achievements"] = unlocked
    save_users(data)
    return newly_unlocked


def get_achievements(username):

    data = load_users()
    user = data["users"].get(username, {})
    unlocked = user.get("achievements", [])

    all_achievements = [
        {"id": "first_win",  "name": "First Blood",  "desc": "Win your first game",           "icon": "🎉"},
        {"id": "ten_wins",   "name": "On a Roll",     "desc": "Win 10 games",                  "icon": "🔥"},
        {"id": "fifty_wins", "name": "Veteran",       "desc": "Win 50 games",                  "icon": "🏆"},
        {"id": "big_win",    "name": "High Roller",   "desc": "Win 500+ chips in one go",      "icon": "💰"},
        {"id": "whale",      "name": "Whale",         "desc": "Win 1000+ chips in one go",     "icon": "🐋"},
        {"id": "played_10",  "name": "Regular",       "desc": "Play 10 games",                 "icon": "🃏"},
        {"id": "played_50",  "name": "Dedicated",     "desc": "Play 50 games",                 "icon": "⭐"},
        {"id": "rich",       "name": "Rich",          "desc": "Hold 2000+ chips at once",      "icon": "💎"},
        {"id": "blackjack",  "name": "Natural",       "desc": "Hit a Blackjack",               "icon": "🃏"},
        {"id": "blackjack5", "name": "Card Sharp",    "desc": "Hit 5 Blackjacks",              "icon": "🎰"},
    ]

    return [
        {**a, "unlocked": a["id"] in unlocked}
        for a in all_achievements
    ]


def get_recent_players(username):
    data = load_users()
    user = data["users"].get(username, {})
    recent = user.get("recent_players", [])
    all_users = data["users"]
    result = []
    for p in recent:
        if p in all_users:
            result.append({
                "username": p,
                "chips": all_users[p].get("chips", 0),
                "wins": all_users[p].get("stats", {}).get("wins", 0),
                "games": all_users[p].get("stats", {}).get("games_played", 0),
            })
    return result