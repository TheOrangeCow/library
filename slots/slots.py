from flask import Blueprint, request, session, render_template, redirect, url_for
from functools import wraps
from auth.auth import get_chips, update_chips, record_result, get_theme
import os, random


slots_bp = Blueprint(
    'slots', __name__,
    template_folder='templates',
    static_folder='static',
    static_url_path='/slots/static'
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "username" not in session:
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return decorated

SYMBOLS = ["🍒", "🍋", "🍊", "🍇", "⭐", "💎", "7️⃣", "🃏"]


SYMBOL_POOL = (
    ["🍒"] * 30 +
    ["🍋"] * 25 +
    ["🍊"] * 20 +
    ["🍇"] * 15 +
    ["⭐"] * 8  +
    ["💎"] * 5  +
    ["7️⃣"] * 3  +
    ["🃏"] * 2
)

PAYOUTS = {
    "🍒": 2,
    "🍋": 3,
    "🍊": 4,
    "🍇": 5,
    "⭐": 10,
    "💎": 20,
    "7️⃣": 50,
    "🃏": 100,
}

TWO_PAYOUTS = {
    "🍒": 0,
    "🍋": 0,
    "🍊": 0,
    "🍇": 0,
    "⭐": 1,
    "💎": 2,
    "7️⃣": 5,
    "🃏": 10,
}

def spin_reel():
    return random.choice(SYMBOL_POOL)

def evaluate(reels, bet):
    s1, s2, s3 = reels
    winnings = 0
    result = "lose"

    if s1 == s2 == s3:
        mult = PAYOUTS.get(s1, 1)
        winnings = bet * mult
        result = "jackpot" if s1 in ("7️⃣", "🃏") else "win"
    elif s1 == s2 or s2 == s3 or s1 == s3:
        if s1 == s2:   sym = s1
        elif s2 == s3: sym = s2
        else:          sym = s1
        mult = TWO_PAYOUTS.get(sym, 0)
        winnings = bet * mult
        result = "win" if winnings > 0 else "lose"
    
    return winnings, result


@slots_bp.route("/slots", methods=["GET", "POST"])
@login_required
def index():
    username = session["username"]
    chips = get_chips(username)
    error = None
    spin_result = None

    if request.method == "POST":
        try:
            bet = int(request.form.get("bet", 0))
        except ValueError:
            bet = 0

        if bet < 1:
            error = "Minimum bet is 1 chip."
        elif bet > chips:
            error = "Not enough chips."
        else:

            update_chips(username, -bet)
            chips -= bet

            reels = [spin_reel(), spin_reel(), spin_reel()]
            winnings, result = evaluate(reels, bet)

            if winnings > 0:
                update_chips(username, winnings)
                chips += winnings

            delta = winnings - bet
            record_result(username, "slots", result, delta)

            spin_result = {
                "reels": reels,
                "bet": bet,
                "winnings": winnings,
                "delta": delta,
                "result": result,
                "chips": get_chips(username),
            }

    return render_template("slots/index.html",
        username=username,
        chips=get_chips(username),
        spin_result=spin_result,
        error=error,
        payouts=PAYOUTS,
        two_payouts=TWO_PAYOUTS,
        theme=get_theme(username),
    )

from flask import jsonify

@slots_bp.route("/slots/spin", methods=["POST"])
@login_required
def spin():
    username = session["username"]
    chips = get_chips(username)
    try:
        bet = int(request.form.get("bet", 0))
    except ValueError:
        bet = 0

    if bet < 1:
        return jsonify({"error": "Minimum bet is 1 chip."})
    if bet > chips:
        return jsonify({"error": "Not enough chips."})

    update_chips(username, -bet)
    reels = [spin_reel(), spin_reel(), spin_reel()]
    winnings, result = evaluate(reels, bet)
    if winnings > 0:
        update_chips(username, winnings)
    delta = winnings - bet
    record_result(username, "slots", result, delta)

    return jsonify({
        "reels": reels,
        "bet": bet,
        "winnings": winnings,
        "delta": delta,
        "result": result,
        "chips": get_chips(username),
    })

