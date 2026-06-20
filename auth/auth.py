from flask import Blueprint, request, session, redirect, url_for, render_template
import json, os, hashlib, time, hmac
import requests
from dotenv import load_dotenv
from datetime import datetime
from auth.plus_checker import is_plus 

auth_bp = Blueprint('auth', __name__, template_folder='templates',static_folder='static', static_url_path='/auth/static')

load_dotenv()

CODE_SECRET  = os.getenv("CODE_SECRET")

COW_ACCOUNTS = "https://theorangecow.org"
COW_CLIENT_ID = "library"
COW_CLIENT_SECRET = "dev-secret-library" #os.getenv("COW_CLIENT_SECRET")
COW_REDIRECT_URI = "https://library.theorangecow.org/cow/callback"

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

def safe_user(user):
    user.setdefault("chips", 0)
    user.setdefault("stats", {
        "games_played": 0,
        "wins": 0,
        "blackjacks": 0,
        "biggest_win": 0,
        "peak_chips": user.get("chips", 0),
    })
    user.setdefault("history", [])
    user.setdefault("friends", [])
    user.setdefault("friend_requests", [])
    user.setdefault("friend_requests_sent", [])
    user.setdefault("achievements", [])
    return user

 
def save_avatar(username, avatar_data):
    data = load_users()
    if username in data["users"]:
        data["users"][username]["avatar"] = avatar_data
        save_users(data)
 
def get_avatar(username):
    data = load_users()
    return data["users"].get(username, {}).get("avatar", None)
 
def get_friends(username):
    data = load_users()
    return data["users"].get(username, {}).get("friends", [])
 
def get_friend_requests(username):
    data = load_users()
    return data["users"].get(username, {}).get("friend_requests", [])

@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"].strip()
        confirm  = request.form["confirm"].strip()
        join_code = request.form.get("join_code", "").strip().upper()

        if username.endswith("_cow"):
            return render_template("auth/register.html", error="Invalid username.")

        if join_code != get_join_code():
            return render_template("auth/register.html", error="Invalid or expired join code.")
        
        if password != confirm:
            return render_template("auth/register.html", error="Passwords do not match.")

        data = load_users()
        if username in data["users"]:
            return render_template("auth/register.html", error="Username already taken.")

        data["users"][username] = {
            "password": hash_pw(password),
            "chips": 1000,
            "stats": {
                "games_played": 0,
                "wins": 0,
                "blackjacks": 0,
                "biggest_win": 0,
                "peak_chips": 1000
            },
            "history": [],
            "friends": [],
            "friend_requests": [],
            "friend_requests_sent": [],
            "achievements": [],
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

        if user and user.get("password") is None:
            return render_template("auth/login.html", error="This account signs in with Login with Cow — use the button below.")

        if not user or user["password"] != hash_pw(password):
            return render_template("auth/login.html", error="Invalid credentials.")
        session["username"] = username
        return redirect(url_for("home"))
    return render_template("auth/login.html")

@auth_bp.route("/cow/login")
def cow_login():
    return redirect(
        f"{COW_ACCOUNTS}/sso/authorize?client_id={COW_CLIENT_ID}&redirect_uri={COW_REDIRECT_URI}"
    )


@auth_bp.route("/cow/callback")
def cow_callback():
    token = request.args.get("token")
    if not token:
        return render_template("auth/login.html", error="Cow sign-in didn't send back a token.")

    try:
        resp = requests.post(
            f"{COW_ACCOUNTS}/sso/verify",
            json={
                "client_id": COW_CLIENT_ID,
                "client_secret": COW_CLIENT_SECRET,
                "token": token,
            },
            timeout=5,
        )
        result = resp.json()
    except (requests.RequestException, ValueError):
        return render_template("auth/login.html", error="Couldn't reach Cow accounts — try again.")

    if resp.status_code != 200 or not result.get("ok"):
        return render_template("auth/login.html", error="Cow sign-in could not be verified.")

    username = result["username"] + "_cow"
    data = load_users()

    if username not in data["users"]:
        data["users"][username] = {
            "password": None,
            "cow_linked": True,
            "chips": 1000,
            "stats": {
                "games_played": 0,
                "wins": 0,
                "blackjacks": 0,
                "biggest_win": 0,
                "peak_chips": 1000
            },
            "history": [],
            "friends": [],
            "friend_requests": [],
            "friend_requests_sent": [],
            "achievements": [],
        }
        save_users(data)

    session["username"] = username
    return redirect(url_for("home"))



@auth_bp.route("/set_theme", methods=["POST"])
def set_theme():
    if "username" not in session:
        return {"ok": False, "error": "Not logged in"}, 401

    theme = request.json.get("theme", "")
    data = load_users()

    username = session["username"]

    if username in data["users"]:
        if theme in ["violet", "silver"] and not is_plus(username):
            return {
                "ok": False,
                "error": "You must have Plus to use this theme."
            }, 200

        data["users"][username]["theme"] = theme
        save_users(data)

    return {"ok": True}

def get_theme(username):
    data = load_users()
    return data["users"].get(username, {}).get("theme", "")

@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))

@auth_bp.route("/settings", methods=["GET", "POST"])
def settings():
    if "username" not in session:
        return redirect(url_for("auth.login"))
 
    username = session["username"]
    error = None
    success = None
 
    if request.method == "POST":
        action = request.form.get("action")
        data = load_users()
        user = data["users"].get(username)
 
        if action == "change_username":
            if user["password"] == None:
                error = "You can't change your username here as your account is externally manged"
            else:
                new_username = request.form.get("new_username", "").strip()
                current_pw   = request.form.get("current_password_u", "").strip()
     
                if not new_username:
                    error = "New username cannot be empty."
                elif user["password"] != hash_pw(current_pw):
                    error = "Current password is incorrect."
                elif new_username in data["users"]:
                    error = "That username is already taken."
                else:
                    data["users"][new_username] = data["users"].pop(username)
                    save_users(data)
                    session["username"] = new_username
                    username = new_username
                    success = f"Username changed to '{new_username}'."
 
        elif action == "change_password":
            if user["password"] == None:
                error = "You can't change your password here as your account is externally manged"
            else:
                current_pw  = request.form.get("current_password_p", "").strip()
                new_pw      = request.form.get("new_password", "").strip()
                confirm_pw  = request.form.get("confirm_password", "").strip()
     
                if user["password"] != hash_pw(current_pw):
                    error = "Current password is incorrect."
                elif len(new_pw) < 4:
                    error = "New password must be at least 4 characters."
                elif new_pw != confirm_pw:
                    error = "New passwords do not match."
                else:
                    data["users"][username]["password"] = hash_pw(new_pw)
                    save_users(data)
                    success = "Password changed successfully."
 
    data = load_users()
    user_data = data["users"].get(username, {})
    return render_template(
        "auth/settings.html",
        theme=get_theme(username),
        username=username,
        chips=user_data.get("chips", 0),
        error=error,
        success=success,
        is_admin=(username == "daniel"),
    )
@auth_bp.route("/api/avatar/<username>")
def api_avatar(username):
    from flask import jsonify
    pixels = get_avatar(username)
    return jsonify({"pixels": pixels})

@auth_bp.route("/profile", methods=["GET", "POST"])
def profile():
    if "username" not in session:
        return redirect(url_for("auth.login"))

    username = session["username"]
    data = load_users()
    user_data = safe_user(data["users"].get(username, {}))

    return render_template(
        "auth/profile.html",
        theme=get_theme(username),
        username=username,
        chips=get_chips(username),
        error=None,
        friend_requests=user_data["friend_requests"],
        friends_list=[
            {
                "username": f,
                "chips": data["users"].get(f, {}).get("chips", 0)
            }
            for f in user_data["friends"]
        ],
        avatar=get_avatar(username),
        achievements=get_achievements(username),
        history=user_data["history"][-20:][::-1],
        stats=user_data["stats"],
    )

@auth_bp.app_template_filter('datetimeformat')
def datetimeformat(value):
    try:
        return datetime.fromtimestamp(int(value)).strftime("%d %b %Y %H:%M")
    except:
        return "—"


@auth_bp.route("/u/<target>")
def view_profile(target):
    if "username" not in session:
        return redirect(url_for("auth.login"))
 
    me = session["username"]
    data = load_users()
 
    if target not in data["users"]:
        return render_template("auth/profile_not_found.html", theme=get_theme(me), username=me), 404
 
    user_data = data["users"][target]
    my_data   = data["users"][me]

    friends         = me in user_data.get("friends", [])
    req_sent        = target in my_data.get("friend_requests_sent", [])
    req_received    = me in user_data.get("friend_requests", [])
 
    achievements_all = get_achievements(target)
    unlocked = [a for a in achievements_all if a["unlocked"]]
 
    history = user_data.get("history", [])[-10:][::-1]
 
    return render_template(
        "auth/view_profile.html",
        theme=get_theme(me),
        me=me,
        target=target,
        chips=user_data.get("chips", 0),
        stats=user_data.get("stats", {}),
        avatar=user_data.get("avatar", None),
        achievements=unlocked,
        history=history,
        friends=friends,
        req_sent=req_sent,
        req_received=req_received,
        friend_count=len(user_data.get("friends", [])),
        is_me=(me == target),
    )
 
 
@auth_bp.route("/friend_request/<target>", methods=["POST"])
def friend_request(target):
    if "username" not in session:
        return redirect(url_for("auth.login"))
    me = session["username"]
    if me == target:
        return redirect(url_for("auth.view_profile", target=target))
 
    data = load_users()
    if target not in data["users"]:
        return redirect(url_for("auth.view_profile", target=target))
 
    reqs = data["users"][target].setdefault("friend_requests", [])
    if me not in reqs:
        reqs.append(me)
 
    sent = data["users"][me].setdefault("friend_requests_sent", [])
    if target not in sent:
        sent.append(target)
 
    save_users(data)
    return redirect(url_for("auth.view_profile", target=target))
 
 
@auth_bp.route("/friend_accept/<requester>", methods=["POST"])
def friend_accept(requester):
    if "username" not in session:
        return redirect(url_for("auth.login"))
    me = session["username"]
    data = load_users()
 
    if requester not in data["users"]:
        return redirect(url_for("auth.profile"))
 
    my_friends = data["users"][me].setdefault("friends", [])
    their_friends = data["users"][requester].setdefault("friends", [])
    if requester not in my_friends:
        my_friends.append(requester)
    if me not in their_friends:
        their_friends.append(me)
 
    reqs = data["users"][me].setdefault("friend_requests", [])
    if requester in reqs:
        reqs.remove(requester)
    sent = data["users"][requester].setdefault("friend_requests_sent", [])
    if me in sent:
        sent.remove(me)
 
    save_users(data)
    return redirect(url_for("auth.profile"))
 
 
@auth_bp.route("/friend_decline/<requester>", methods=["POST"])
def friend_decline(requester):
    if "username" not in session:
        return redirect(url_for("auth.login"))
    me = session["username"]
    data = load_users()
 
    reqs = data["users"][me].setdefault("friend_requests", [])
    if requester in reqs:
        reqs.remove(requester)
    if requester in data["users"]:
        sent = data["users"][requester].setdefault("friend_requests_sent", [])
        if me in sent:
            sent.remove(me)
 
    save_users(data)
    return redirect(url_for("auth.profile"))
 
 
@auth_bp.route("/friend_remove/<target>", methods=["POST"])
def friend_remove(target):
    if "username" not in session:
        return redirect(url_for("auth.login"))
    me = session["username"]
    data = load_users()
 
    if me in data["users"]:
        friends = data["users"][me].setdefault("friends", [])
        if target in friends:
            friends.remove(target)
    if target in data["users"]:
        friends = data["users"][target].setdefault("friends", [])
        if me in friends:
            friends.remove(me)
 
    save_users(data)
    return redirect(url_for("auth.view_profile", target=target))
 
 
@auth_bp.route("/send_chips/<target>", methods=["POST"])
def send_chips(target):
    if "username" not in session:
        return redirect(url_for("auth.login"))
    me = session["username"]
    if me == target:
        return redirect(url_for("auth.view_profile", target=target))
 
    try:
        amount = int(request.form.get("amount", 0))
    except ValueError:
        return redirect(url_for("auth.view_profile", target=target))
 
    if amount <= 0:
        return redirect(url_for("auth.view_profile", target=target))
 
    data = load_users()
    if target not in data["users"]:
        return redirect(url_for("auth.view_profile", target=target))
 
    my_chips = data["users"][me].get("chips", 0)
    amount = min(amount, my_chips)
 
    data["users"][me]["chips"] = my_chips - amount
    data["users"][target]["chips"] = data["users"][target].get("chips", 0) + amount
    save_users(data)
 
    return redirect(url_for("auth.view_profile", target=target))
 
 
@auth_bp.route("/save_avatar", methods=["POST"])
def save_avatar_route():
    if "username" not in session:
        return {"ok": False}, 401
    pixels = request.json.get("pixels", [])
    if len(pixels) != 256:
        return {"ok": False, "error": "bad pixel count"}, 400
    save_avatar(session["username"], pixels)
    return {"ok": True}

@auth_bp.route("/admin", methods=["GET", "POST"])
def admin():
    
    if "username" not in session or session["username"] != "daniel":
        return redirect(url_for("home"))
    username = "daniel"
    error = None
    success = None
 
    if request.method == "POST":
        action      = request.form.get("action")
        target_user = request.form.get("target_user", "").strip()
        data = load_users()
 
        if target_user not in data["users"]:
            error = f"User '{target_user}' not found."
        else:
            if action == "admin_change_username":
                new_username = request.form.get("admin_new_username", "").strip()
                if not new_username:
                    error = "New username cannot be empty."
                elif new_username in data["users"]:
                    error = "That username is already taken."
                else:
                    data["users"][new_username] = data["users"].pop(target_user)
                    save_users(data)
                    success = f"Renamed '{target_user}' → '{new_username}'."
 
            elif action == "admin_change_password":
                new_pw      = request.form.get("admin_new_password", "").strip()
                confirm_pw  = request.form.get("admin_confirm_password", "").strip()
                if len(new_pw) < 4:
                    error = "Password must be at least 4 characters."
                elif new_pw != confirm_pw:
                    error = "Passwords do not match."
                else:
                    data["users"][target_user]["password"] = hash_pw(new_pw)
                    save_users(data)
                    success = f"Password updated for '{target_user}'."
 
            elif action == "admin_set_chips":
                try:
                    chips = int(request.form.get("admin_chips", 0))
                    data["users"][target_user]["chips"] = chips
                    save_users(data)
                    success = f"Set chips for '{target_user}' to {chips}."
                except ValueError:
                    error = "Chips must be a whole number."
 
    data = load_users()
    users_list = [
        {
            "username": u,
            "chips": info.get("chips", 0),
            "wins": info.get("stats", {}).get("wins", 0),
            "games": info.get("stats", {}).get("games_played", 0),
        }
        for u, info in data["users"].items()
    ]
    users_list.sort(key=lambda x: x["username"].lower())
 
    return render_template(
        "auth/admin.html",
        theme=get_theme(username),
        users_list=users_list,
        error=error,
        success=success,
    )

def get_chips(username):
    data = load_users()
    return data["users"].get(username, {}).get("chips", 0)

def update_chips(username, amount):
    data = load_users()
    if username in data["users"]:
        data["users"][username]["chips"] = max(0, data["users"][username]["chips"] + amount)
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
