#!/usr/bin/env python3
"""Dama Drop web app: serves the frontend and JSON APIs."""
import json
import os
import re
import sqlite3
import urllib.request
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")
STATIC = os.path.join(BASE, "static")
DB = os.path.join(DATA, "subscribers.db")
UA = {"User-Agent": "Mozilla/5.0 (DamaDrop)"}

app = FastAPI(title="Dama Drop")

KNOWN_SHOPS = {
    "sweetskendamas.com": ("sweets", "Sweets Kendamas"),
    "kromkendama.com": ("krom", "KROM"),
    "graintheory.com": ("grain-theory", "Grain Theory"),
    "erratickendamas.com": ("erratic", "Erratic Kendamas"),
    "kendamausa.com": ("kendama-usa", "Kendama USA"),
}


def db():
    os.makedirs(DATA, exist_ok=True)
    con = sqlite3.connect(DB)
    con.execute(
        "CREATE TABLE IF NOT EXISTS subscribers ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT NOT NULL, "
        "kind TEXT NOT NULL, target TEXT NOT NULL DEFAULT '', "
        "created_at TEXT NOT NULL, UNIQUE(email, kind, target))"
    )
    return con


def read_json(name, default):
    path = os.path.join(DATA, name)
    if not os.path.exists(path):
        return default
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return default


@app.get("/")
def index():
    return FileResponse(os.path.join(STATIC, "index.html"))


@app.get("/api/snapshot")
def snapshot():
    return JSONResponse(read_json("snapshot.json",
                                  {"updated_at": None, "brands": [], "products": []}))


@app.get("/api/events")
def events():
    return JSONResponse(read_json("events.json", [])[::-1][:60])


@app.get("/api/lookup")
def lookup(url: str):
    """Paste a kendama product link -> product info + stock + buy link."""
    m = re.search(r"https?://([^/]+)/products/([a-z0-9\-]+)", url.strip(), re.I)
    if not m:
        raise HTTPException(400, "That doesn't look like a product link. "
                                 "Paste a link to a specific kendama product page.")
    host, handle = m.group(1).lower(), m.group(2).lower()
    api_url = f"https://{host}/products/{handle}.js"
    req = urllib.request.Request(api_url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            p = json.load(r)
    except Exception:
        raise HTTPException(422, "Couldn't read that product page. "
                                 "It may be sold from a store we can't check automatically.")

    variants = p.get("variants", []) or []
    prices, available = [], False
    options = []
    for v in variants:
        try:
            prices.append(float(v.get("price", 0) or 0) / 100.0)
        except (TypeError, ValueError):
            pass
        if v.get("available"):
            available = True
        options.append({"title": v.get("title"), "available": bool(v.get("available"))})

    brand_id, brand_name = KNOWN_SHOPS.get(host, (None, None))
    return {
        "title": p.get("title"),
        "brand": brand_name,
        "brand_id": brand_id,
        "price": min(prices) if prices else None,
        "available": available,
        "image": p.get("featured_image"),
        "url": f"https://{host}/products/{handle}",
        "product_id": f"{brand_id}:{p.get('id')}" if brand_id else None,
        "options": options[:12],
    }


class Subscribe(BaseModel):
    email: str
    kind: str  # 'product' | 'brand' | 'drops'
    target: str = ""  # product url/id, brand id, or ''


@app.post("/api/subscribe")
def subscribe(s: Subscribe):
    email = s.email.strip().lower()
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        raise HTTPException(400, "That email doesn't look right.")
    if s.kind not in ("product", "brand", "drops"):
        raise HTTPException(400, "Unknown alert type.")
    con = db()
    try:
        con.execute(
            "INSERT INTO subscribers (email, kind, target, created_at) VALUES (?,?,?,?)",
            (email, s.kind, s.target.strip(),
             datetime.now(timezone.utc).isoformat()),
        )
        con.commit()
    except sqlite3.IntegrityError:
        pass
    finally:
        con.close()
    return {"ok": True}


app.mount("/static", StaticFiles(directory=STATIC), name="static")


# On hosted deployments (Render etc.), run the stock checker + notifier
# inside the web process on a schedule. Enabled via RUN_SCHEDULER=1 env var.
if os.environ.get("RUN_SCHEDULER") == "1":
    from apscheduler.schedulers.background import BackgroundScheduler

    def _scheduled_check():
        try:
            import checker
            import notify
            checker.main()
            notify.main()
        except Exception as e:  # never take the web server down
            print("scheduled stock check failed:", e)

    _sched = BackgroundScheduler()
    _sched.add_job(_scheduled_check, "interval", hours=1)
    _sched.start()
