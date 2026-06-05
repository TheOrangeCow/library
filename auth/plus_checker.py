def is_plus(username: str) -> bool:
    data = load_users()
    user = data["users"].get(username, {})
    plus = user.get("plus", {})
    if not plus.get("active"):
        return False
    if plus.get("expires_at") and time.time() > plus["expires_at"]:
        return False
    return True