#!/usr/bin/env python3
"""
One-shot availability check for GitHub Actions (stdlib only).
Secrets come from environment variables, nothing sensitive lives in this file.

State (state.json) remembers which days were already announced and whether a
"session expired" alert was already sent, so you don't get spammed every run.
"""
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta

try:
    from zoneinfo import ZoneInfo
    TZ = ZoneInfo("Europe/Prague")
except Exception:
    TZ = None

BASE = "https://scandic.cleverq.de/api/external/v4/sites/3/appointments/available_days"
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36")
STATE_FILE = "state.json"


def env(name, default=None):
    v = os.environ.get(name, default)
    if v is None or not str(v).strip():
        sys.exit(f"Missing required setting: {name}")
    return str(v).strip().strip('"').strip("'")


SESSION_COOKIE = env("SESSION_COOKIE")
BOOKING_SESSION_KEY = env("BOOKING_SESSION_KEY")
NOT_PUBLIC_TOKEN = env("NOT_PUBLIC_TOKEN")
NTFY_TOPIC = env("NTFY_TOPIC")
CURRENT_APPOINTMENT = date.fromisoformat(env("CURRENT_APPOINTMENT", "2026-11-02"))
SERVICE_ID = env("SERVICE_ID", "20")
SUBTASK_ITEMS = env("SUBTASK_ITEMS", '{"subtask_id":46,"number":1}')


def today():
    return datetime.now(TZ).date() if TZ else date.today()


def notify(title, message):
    print(f"[NOTIFY] {title}: {message}")
    try:
        req = urllib.request.Request(
            f"https://ntfy.sh/{NTFY_TOPIC}",
            data=message.encode("utf-8"),
            headers={"Title": title, "Priority": "high"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=15).read()
    except Exception as e:
        print(f"Could not send notification: {e}")


def fetch_days():
    params = [
        ("service_id", SERVICE_ID),
        ("from_day", today().isoformat()),
        ("to_day", (CURRENT_APPOINTMENT - timedelta(days=1)).isoformat()),
        ("subtask_items[]", SUBTASK_ITEMS),
        ("booking_session_key", BOOKING_SESSION_KEY),
        ("not_publicy_listed_token", NOT_PUBLIC_TOKEN),
    ]
    req = urllib.request.Request(
        BASE + "?" + urllib.parse.urlencode(params),
        headers={
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "User-Agent": USER_AGENT,
            "Cookie": f"_scandic_session={SESSION_COOKIE}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")


def load_state():
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            s = json.load(f)
    except (OSError, ValueError):
        s = {}
    s.setdefault("notified_days", [])
    s.setdefault("session_alert_sent", False)
    return s


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, sort_keys=True)
        f.write("\n")


def parse_days(data):
    days = []
    for item in data.get("available_days", []):
        s = item.get("day") if isinstance(item, dict) else item
        try:
            days.append(date.fromisoformat(str(s)))
        except ValueError:
            continue
    return days


def main():
    state = load_state()
    status, text = fetch_days()
    now = datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S") if TZ else datetime.now().isoformat()

    try:
        data = json.loads(text)
    except ValueError:
        data = None

    if status != 200 or not isinstance(data, dict) or "available_days" not in data:
        print(f"[{now}] Unexpected response: HTTP {status}: {text[:200]}")
        if not state["session_alert_sent"]:
            notify("SIRI checker needs attention",
                   f"Got HTTP {status}. The session may have expired. "
                   "Update the GitHub secrets with fresh values.")
            state["session_alert_sent"] = True
        save_state(state)
        return

    state["session_alert_sent"] = False
    early = sorted(d for d in parse_days(data) if today() <= d < CURRENT_APPOINTMENT)
    early_iso = [d.isoformat() for d in early]
    new = [d for d in early if d.isoformat() not in state["notified_days"]]

    if new:
        nice = ", ".join(d.strftime("%a %d %b") for d in new)
        notify("Earlier SIRI slot available!",
               f"Open days before {CURRENT_APPOINTMENT:%d %b}: {nice}. "
               "Go change your appointment now.")
    else:
        print(f"[{now}] Nothing new before {CURRENT_APPOINTMENT}. Currently open: {early_iso or 'none'}")

    # Remember only what is open right now, so a day that disappears and
    # comes back later triggers a fresh alert.
    state["notified_days"] = early_iso
    save_state(state)


if __name__ == "__main__":
    main()
