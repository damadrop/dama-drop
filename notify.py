#!/usr/bin/env python3
"""Dama Drop notifier.

Reads new stock events (restocks / new drops) since the last run and emails
matching subscribers.

- The site owner's alerts go out through the owner's connected Gmail.
- Other subscribers are queued in data/outbox.json until an email-service
  API key (e.g. Resend) is configured in data/config.json.
"""
import json
import os
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")
DB = os.path.join(DATA, "subscribers.db")


def load(name, default):
    p = os.path.join(DATA, name)
    if os.path.exists(p):
        try:
            with open(p) as f:
                return json.load(f)
        except Exception:
            pass
    return default


def save(name, obj):
    with open(os.path.join(DATA, name), "w") as f:
        json.dump(obj, f)


def gmail_send(to, subject, body):
    cmd = ["hatch_gws_cli", "gmail", "+send",
           "--to", to, "--subject", subject, "--body", body]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    return r.returncode == 0, (r.stdout + r.stderr)[-500:]


def resend_send(api_key, to, subject, body):
    import urllib.request
    payload = json.dumps({
        "from": "Dama Drop <alerts@damadrop.app>",
        "to": [to],
        "subject": subject,
        "text": body,
    }).encode()
    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=payload,
        headers={"Authorization": f"Bearer {api_key}",
                 "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status == 200, ""
    except Exception as e:
        return False, str(e)[-300:]


def matches(sub, ev):
    kind, target = sub["kind"], (sub["target"] or "").strip().lower()
    p = ev.get("product", {})
    pid = (p.get("id") or "").lower()
    purl = (p.get("url") or "").lower()
    pbrand = (p.get("brand") or "").lower()
    if kind == "drops":
        return ev["type"] == "new_drop"
    if kind == "brand":
        return target in (pbrand, pid.split(":")[0]) and ev["type"] in ("restock", "new_drop")
    if kind == "product":
        return target in (pid, purl) and ev["type"] == "restock"
    return False


def main():
    cfg = load("config.json", {})
    owner_email = (os.environ.get("OWNER_EMAIL") or cfg.get("owner_email") or "").strip().lower()
    resend_key = os.environ.get("RESEND_API_KEY") or cfg.get("resend_api_key")
    state = load("notify_state.json", {"last_at": None})
    last_at = state.get("last_at")

    events = [e for e in load("events.json", [])
              if not last_at or e.get("at", "") > last_at]
    if not events:
        print("no new events")
        return

    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    subs = [dict(r) for r in con.execute("SELECT * FROM subscribers")]
    con.close()
    if not subs:
        print(f"{len(events)} new events, no subscribers yet")

    outbox = load("outbox.json", [])
    brand_names = {b["id"]: b["name"] for b in
                   load("snapshot.json", {}).get("brands", [])}

    for s in subs:
        hits = [e for e in events if matches(s, e)]
        if not hits:
            continue
        lines = []
        for e in hits:
            p = e["product"]
            what = "Back in stock" if e["type"] == "restock" else "New drop"
            bn = brand_names.get(p.get("brand"), p.get("brand", ""))
            lines.append(f"- {what}: {p.get('title')} ({bn}) {p.get('url')}")
        subject = f"Dama Drop: {len(hits)} kendama alert{'s' if len(hits) != 1 else ''}"
        body = ("Heads up from Dama Drop:\n\n" + "\n".join(lines) +
                "\n\nBrowse everything: see the site.\n"
                "You're getting this because you asked for kendama stock alerts.")

        if resend_key:
            ok, info = resend_send(resend_key, s["email"], subject, body)
            print(f"resend -> {s['email']}: {'sent' if ok else 'FAILED: ' + info}")
        elif owner_email and s["email"].lower() == owner_email:
            ok, info = gmail_send(s["email"], subject, body)
            print(f"owner alert -> {s['email']}: {'sent' if ok else 'FAILED: ' + info}")
        else:
            outbox.append({"to": s["email"], "subject": subject,
                           "body": body, "at": datetime.now(timezone.utc).isoformat()})
            print(f"queued for {s['email']} (no email-service key yet)")

    save("outbox.json", outbox)
    newest = max(e.get("at", "") for e in events)
    save("notify_state.json", {"last_at": newest})
    print(f"processed {len(events)} events for {len(subs)} subscribers")


if __name__ == "__main__":
    sys.exit(main())
