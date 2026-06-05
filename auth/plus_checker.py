USERS_FILE = os.path.join(os.path.dirname(__file__), "users.json")

def load_users():
    if not os.path.exists(USERS_FILE):
        return {"users": {}}
    with open(USERS_FILE) as f:
        return json.load(f)


def is_plus(username: str) -> bool:
    data = load_users()
    user = data["users"].get(username, {})
    plus = user.get("plus", {})
    if not plus.get("active"):
        return False
    if plus.get("expires_at") and time.time() > plus["expires_at"]:
        return False
    return True