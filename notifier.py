from __future__ import annotations
import json, urllib.request
from storage import get_secret

def _post_json(url, payload):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.status

def send_telegram(message):
    token = get_secret("TELEGRAM_BOT_TOKEN")
    chat_id = get_secret("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return False, "not-configured"
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        _post_json(url, {"chat_id": chat_id, "text": message})
        return True, "telegram"
    except Exception as e:
        return False, type(e).__name__

def send_discord(message):
    webhook = get_secret("DISCORD_WEBHOOK_URL")
    if not webhook:
        return False, "not-configured"
    try:
        _post_json(webhook, {"content": message})
        return True, "discord"
    except Exception as e:
        return False, type(e).__name__

def notify(message):
    ok,target = send_telegram(message)
    if ok:
        return True,target
    ok2,target2 = send_discord(message)
    if ok2:
        return True,target2
    return False,f"{target}/{target2}"
