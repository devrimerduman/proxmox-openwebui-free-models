#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Proxmox OpenWebUI Free Models Activator

This script ensures that only **free** models from OpenRouter
remain active inside OpenWebUI. Paid models are automatically
disabled. When new models are released, the script will check
them and activate only those that are free.

Usage:
  OPENROUTER_API_KEY="..." python3 proxmox_openwebui_free_models.py --apply
  # dry-run (preview changes without writing):
  OPENROUTER_API_KEY="..." python3 proxmox_openwebui_free_models.py

Arguments:
  --db /absolute/path/webui.db   specify database path if auto-detection fails
  --apply                        actually update the database (otherwise dry-run)
  --verbose                      print detailed output
"""

import os
import sys
import json
import sqlite3
import argparse
import urllib.request
from urllib.error import HTTPError, URLError

DEFAULT_DB_CANDIDATES = [
    "/app/data/webui.db",
    "/data/webui.db",
    "/var/lib/open-webui/webui.db",
    "/root/.cache/open-webui/webui.db",
    "/opt/open-webui/data/webui.db",
]

OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"


def http_json(url, headers):
    """Perform HTTP GET and parse JSON response."""
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def is_price_zero(x):
    """Check if price value is zero or None."""
    if x is None:
        return True
    try:
        return float(x) == 0.0
    except Exception:
        return False


def infer_is_free(model_obj):
    """
    Determine if a model is free.

    Rules:
    - If model ID contains ':free', '-free', '(free)', treat as free
    - If pricing fields are all zero/None, treat as free
    - If any pricing field > 0, treat as paid
    """
    mid = model_obj.get("id", "") or ""
    if ":free" in mid or mid.endswith("/free") or mid.endswith("-free") or mid.endswith(" (free)"):
        return True

    pricing = model_obj.get("pricing") or {}
    numeric_values = []
    for k, v in pricing.items():
        if isinstance(v, dict):
            numeric_values.extend(v.values())
        else:
            numeric_values.append(v)

    for v in numeric_values:
        if v is None:
            continue
        try:
            if float(v) > 0.0:
                return False
        except Exception:
            pass
    return True


def find_db_path(forced_path=None, verbose=False):
    """Find the path to OpenWebUI database."""
    if forced_path:
        if os.path.isfile(forced_path):
            return forced_path
        raise FileNotFoundError(f"Database not found: {forced_path}")

    env_path = os.environ.get("OPENWEBUI_DB")
    if env_path and os.path.isfile(env_path):
        return env_path

    for p in DEFAULT_DB_CANDIDATES:
        if os.path.isfile(p):
            if verbose:
                print(f"[i] Database found: {p}")
            return p

    raise FileNotFoundError(
        "webui.db not found. Use --db /path/to/webui.db or "
        "run 'find / -name webui.db 2>/dev/null'."
    )


def detect_model_table_and_columns(conn):
    """Detect table and columns in OpenWebUI DB (schema varies by version)."""
    cur = conn.cursor()
    table_candidates = []
    for row in cur.execute("SELECT name FROM sqlite_schema WHERE type='table'"):
        tname = row[0]
        if tname.lower() in ("model", "models"):
            table_candidates.append(tname)

    if not table_candidates:
        raise RuntimeError("Model table not found (expected: model/models).")

    table = table_candidates[0]

    cur.execute(f"PRAGMA table_info({table})")
    cols = [r[1].lower() for r in cur.fetchall()]

    def pick(*names):
        for n in names:
            if n in cols:
                return n
        return None

    id_col = pick("id", "name", "model_id", "model", "slug")
    active_col = pick("is_active", "active", "enabled")
    public_col = pick("is_public", "public", "visible")
    provider_col = pick("provider", "source", "origin", "vendor")
    source_col = pick("source", "provider")

    if not id_col or not active_col:
        raise RuntimeError(f"Required columns missing. Found: {cols}")

    return (table, id_col, active_col, public_col, provider_col, source_col)


def normalize_mid(mid: str):
    """Normalize model IDs for comparison."""
    m = (mid or "").strip().lower()
    if m.startswith("openrouter/"):
        m = m[len("openrouter/") :]
    return m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", help="Path to webui.db")
    ap.add_argument("--apply", action="store_true", help="Apply changes (otherwise dry-run)")
    ap.add_argument("--verbose", action="store_true", help="Verbose output")
    args = ap.parse_args()

    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        print("ERROR: Set OPENROUTER_API_KEY environment variable.", file=sys.stderr)
        sys.exit(1)

    # 1) Fetch OpenRouter models
    headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
    try:
        data = http_json(OPENROUTER_MODELS_URL, headers=headers)
    except (HTTPError, URLError) as e:
        print(f"ERROR: OpenRouter API request failed: {e}", file=sys.stderr)
        sys.exit(2)

    models = data.get("data") or data.get("models") or []
    if args.verbose:
        print(f"[i] Models from OpenRouter: {len(models)}")

    free_ids, paid_ids = set(), set()
    for m in models:
        mid = m.get("id", "")
        if not mid:
            continue
        if infer_is_free(m):
            free_ids.add(normalize_mid(mid))
        else:
            paid_ids.add(normalize_mid(mid))

    if args.verbose:
        print(f"[i] FREE: {len(free_ids)} | PAID: {len(paid_ids)}")

    # 2) Connect to DB
    db_path = find_db_path(args.db, verbose=args.verbose)
    if args.verbose:
        print(f"[i] Using DB: {db_path}")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    try:
        table, id_col, active_col, public_col, provider_col, source_col = detect_model_table_and_columns(conn)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(3)

    cur = conn.cursor()
    where_openrouter = ""
    if provider_col:
        where_openrouter = f"LOWER({provider_col}) LIKE '%openrouter%'"
    elif source_col:
        where_openrouter = f"LOWER({source_col}) LIKE '%openrouter%'"
    else:
        where_openrouter = "1=1"

    rows = list(cur.execute(f"SELECT {id_col} AS mid, {active_col} AS is_active FROM {table} WHERE {where_openrouter}"))
    if args.verbose:
        print(f"[i] OpenRouter models in DB: {len(rows)}")

    to_active, to_inactive = [], []
    for r in rows:
        db_mid_raw = r["mid"]
        norm = normalize_mid(str(db_mid_raw or ""))
        candidates = {norm, norm.replace(":", "/"), norm.replace("/", ":"), norm.replace(" ", ""), norm.replace("openai/", "")}
        is_free = any((c in free_ids) for c in candidates)
        if is_free:
            to_active.append(db_mid_raw)
        else:
            if any((c in paid_ids) for c in candidates) or len(free_ids) > 0:
                to_inactive.append(db_mid_raw)

    print(f"FREE → activate: {len(to_active)}")
    print(f"PAID → deactivate: {len(to_inactive)}")

    if not args.apply:
        print("\n(dry-run mode; use --apply to write changes)")
        return

    cur.execute("BEGIN")
    if to_inactive:
        ph = ",".join(["?"] * len(to_inactive))
        cur.execute(f"UPDATE {table} SET {active_col}=0 WHERE {id_col} IN ({ph})", to_inactive)
    if to_active:
        ph = ",".join(["?"] * len(to_active))
        cur.execute(f"UPDATE {table} SET {active_col}=1 WHERE {id_col} IN ({ph})", to_active)
    conn.commit()

    print("✅ Updated database: only FREE models are active.")

    if public_col:
        cur.execute("BEGIN")
        if to_inactive:
            ph = ",".join(["?"] * len(to_inactive))
            cur.execute(f"UPDATE {table} SET {public_col}=0 WHERE {id_col} IN ({ph})", to_inactive)
        if to_active:
            ph = ",".join(["?"] * len(to_active))
            cur.execute(f"UPDATE {table} SET {public_col}=1 WHERE {id_col} IN ({ph})", to_active)
        conn.commit()
        print("ℹ️  Public column also updated accordingly.")

    conn.close()
    print("Done.")


if __name__ == "__main__":
    main()
