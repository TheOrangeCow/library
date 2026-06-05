from flask import Blueprint, request, session, redirect, url_for, render_template
import time
from auth.auth import load_users, save_users, get_chips, get_theme, hash_pw
from auth.plus_checker import is_plus

plus_bp = Blueprint('plus', __name__, template_folder='templates', static_folder='static', static_url_path='/plus/static')

PLUS_UPFRONT_COST = 1000
PLUS_MONTHLY_COST = 10





def get_plus_info(username: str) -> dict:
    data = load_users()
    return data["users"].get(username, {}).get("plus", {})


def charge_monthly_if_due(username: str):
    data = load_users()
    user = data["users"].get(username)
    if not user:
        return
    plus = user.get("plus", {})
    if not plus.get("active"):
        return

    now = time.time()
    next_bill = plus.get("next_billing", 0)

    if now >= next_bill:
        chips = user.get("chips", 0)
        if chips >= PLUS_MONTHLY_COST:
            user["chips"] = chips - PLUS_MONTHLY_COST
            plus["next_billing"] = next_bill + 30 * 24 * 3600
            plus["expires_at"]   = plus["next_billing"]
        else:
            plus["active"] = False
            plus["cancelled_at"] = now
        user["plus"] = plus
        save_users(data)


@plus_bp.route("/plus")
def plus_page():
    if "username" not in session:
        return redirect(url_for("auth.login"))

    username = session["username"]
    charge_monthly_if_due(username)

    plus_info = get_plus_info(username)
    return render_template(
        "auth/plus.html",
        theme=get_theme(username),
        username=username,
        chips=get_chips(username),
        is_plus=is_plus(username),
        next_billing=plus_info.get("next_billing", 0),
        error=request.args.get("error"),
        success=request.args.get("success"),
    )


@plus_bp.route("/plus/subscribe", methods=["POST"])
def subscribe():
    if "username" not in session:
        return redirect(url_for("auth.login"))

    username = session["username"]

    if is_plus(username):
        return redirect(url_for("plus.plus_page") + "?error=You+are+already+a+Plus+member.")

    data = load_users()
    user = data["users"].get(username)
    if not user:
        return redirect(url_for("auth.login"))

    chips = user.get("chips", 0)
    if chips < PLUS_UPFRONT_COST:
        return redirect(url_for("plus.plus_page") + f"?error=Not+enough+chips.+You+need+{PLUS_UPFRONT_COST}.")

    now = time.time()
    next_bill = now + 30 * 24 * 3600

    user["chips"] = chips - PLUS_UPFRONT_COST
    user["plus"] = {
        "active":       True,
        "subscribed_at": now,
        "next_billing":  next_bill,
        "expires_at":    next_bill,
        "cancelled_at":  None,
    }
    save_users(data)

    return redirect(url_for("plus.plus_page") + "?success=Welcome+to+Plus!")


@plus_bp.route("/plus/cancel", methods=["POST"])
def cancel():
    if "username" not in session:
        return redirect(url_for("auth.login"))

    username = session["username"]

    if not is_plus(username):
        return redirect(url_for("plus.plus_page") + "?error=You+don%27t+have+an+active+Plus+subscription.")

    data = load_users()
    user = data["users"].get(username)
    if user and user.get("plus"):
        user["plus"]["active"]       = False
        user["plus"]["cancelled_at"] = time.time()
        save_users(data)

    return redirect(url_for("plus.plus_page") + "?success=Plus+cancelled.+Access+remains+until+your+billing+date.")