#!/usr/bin/env python3
"""Kendama stock checker.

Polls each brand's store API, writes data/snapshot.json, and detects
restocks + new products since the last run (data/state.json).
Alert delivery to subscribers happens in notify.py (separate step).
"""
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")

BRANDS = [
    {"id": "sweets", "name": "Sweets Kendamas", "site": "https://sweetskendamas.com",
     "api": "shopify", "live": True},
    {"id": "krom", "name": "KROM", "site": "https://kromkendama.com",
     "api": "shopify", "live": True},
    {"id": "grain-theory", "name": "Grain Theory", "site": "https://graintheory.com",
     "api": "shopify", "live": True},
    {"id": "erratic", "name": "Erratic Kendamas", "site": "https://erratickendamas.com",
     "api": "shopify", "live": True},
    {"id": "kendama-usa", "name": "Kendama USA", "site": "https://kendamausa.com",
     "api": "none", "live": False,
     "note": "Kendama USA loads its shop with JavaScript, so live stock can't be read automatically. Browse their latest drops below.",
     "links": [
         {"label": "New releases", "url": "https://kendamausa.com/collections/recent-kendama-releases-new"},
         {"label": "Best for beginners", "url": "https://kendamausa.com/collections/best-kendamas-for-beginners"},
         {"label": "Top rated", "url": "https://kendamausa.com/collections/top-rated-kendamas"},
     ]},
]

UA = {"User-Agent": "Mozilla/5.0 (DamaDrop stock checker)"}


def fetch_shopify_products(base):
    products = []
    page = 1
    while True:
        url = f"{base}/products.json?limit=250&page={page}"
        req = urllib.request.Request(url, headers=UA)
        try:
            with urllib.request.urlopen(req, timeout=40) as r:
                data = json.load(r)
        except Exception as e:
            print(f"  !! failed page {page} of {base}: {e}", file=sys.stderr)
            break
        batch = data.get("products", [])
        products.extend(batch)
        if len(batch) < 250:
            break
        page += 1
    return products


def normalize(brand_id, site, p):
    variants = p.get("variants", []) or []
    prices = []
    available = False
    for v in variants:
        try:
            prices.append(float(v.get("price", 0) or 0))
        except (TypeError, ValueError):
            pass
        if v.get("available"):
            available = True
    images = p.get("images", []) or []
    return {
        "id": f"{brand_id}:{p.get('id')}",
        "brand": brand_id,
        "title": p.get("title", "").strip(),
        "handle": p.get("handle", ""),
        "url": f"{site}/products/{p.get('handle', '')}",
        "price": min(prices) if prices else 0,
        "available": available,
        "image": images[0].get("src") if images else None,
        "type": (p.get("product_type") or "").strip(),
        "tags": ([t.strip() for t in p.get("tags", []) if t.strip()]
                 if isinstance(p.get("tags"), list)
                 else [t.strip() for t in (p.get("tags") or "").split(",") if t.strip()]),
    }


def main():
    os.makedirs(DATA, exist_ok=True)
    all_products = []
    for b in BRANDS:
        if b["api"] != "shopify":
            print(f"[{b['id']}] skipped (no machine-readable API)")
            continue
        print(f"[{b['id']}] fetching {b['site']} ...")
        raw = fetch_shopify_products(b["site"])
        normed = [normalize(b["id"], b["site"], p) for p in raw]
        # drop empty-title junk
        normed = [p for p in normed if p["title"]]
        print(f"[{b['id']}] {len(normed)} products")
        all_products.extend(normed)

    now = datetime.now(timezone.utc).isoformat()
    snapshot = {
        "updated_at": now,
        "brands": [{k: v for k, v in b.items() if k != "api"} for b in BRANDS],
        "products": all_products,
    }
    with open(os.path.join(DATA, "snapshot.json"), "w") as f:
        json.dump(snapshot, f)

    # diff vs previous state
    state_path = os.path.join(DATA, "state.json")
    prev = {}
    first_run = not os.path.exists(state_path)
    if not first_run:
        with open(state_path) as f:
            prev = json.load(f).get("products", {})

    cur = {p["id"]: p["available"] for p in all_products}
    restocks, new_drops = [], []
    id_to_product = {p["id"]: p for p in all_products}
    for pid, avail in cur.items():
        if pid not in prev:
            if avail:
                new_drops.append(id_to_product[pid])
        elif avail and not prev[pid]:
            restocks.append(id_to_product[pid])

    with open(state_path, "w") as f:
        json.dump({"updated_at": now, "products": cur}, f)

    events_path = os.path.join(DATA, "events.json")
    events = []
    if os.path.exists(events_path):
        with open(events_path) as f:
            try:
                events = json.load(f)
            except Exception:
                events = []
    if not first_run:
        # First run just establishes the baseline; nothing is "new".
        for p in restocks:
            events.append({"type": "restock", "at": now, "product": p})
        for p in new_drops:
            events.append({"type": "new_drop", "at": now, "product": p})
    events = events[-500:]
    with open(events_path, "w") as f:
        json.dump(events, f)

    print(f"done: {len(all_products)} products, "
          f"{len(restocks)} restocks, {len(new_drops)} new drops")
    return {"restocks": restocks, "new_drops": new_drops}


if __name__ == "__main__":
    main()
