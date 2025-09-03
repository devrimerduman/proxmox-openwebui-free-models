#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Proxmox OpenWebUI Free Models - Allowlist Writer

Writes only FREE OpenRouter model IDs into OpenWebUI's config DB:
config.data.openai.api_configs[<index>].model_ids = [free IDs...]

Usage:
  export OPENROUTER_API_KEY="sk-or-v1-..."
  python3 proxmox_openwebui_free_models.py --db /opt/open-webui/backend/data/webui.db --verbose
  python3 proxmox_openwebui_free_models.py --db /opt/open-webui/backend/data/webui.db --apply --verbose

Options:
  --db PATH              Path to webui.db (required)
  --config-index INDEX   openai.api_configs index to write (default: 0)
  --apply                Write changes (otherwise dry-run)
  --verbose              Verbose output
"""

import os
import sys
import json
import sqlite3
import argparse
import urllib.request
from urllib.error import URLError, HTTPError

OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"


def http_json(url, headers):
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def is_free_model(model_obj):
    mid = model_obj.get("id", "") or ""
    if (":free" in mid) or mid.endswith("/free") or mid.endswith("-free") or mid.endswith(" (free)"):
        return True
    pricing = model_obj.get("pricing") or {}
    values = []
    for v in pricing.values():
        if isinstance(v, dict):
            values.extend(v.values())
        else:
            values.append(v)
    for v in values:
        if v is None:
            continue
        try:
            if float(v) > 0.0:
                return False
        except Exception:
            pass
    return True


def fetch_free_ids(api_key):
    headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
    data = http_json(OPENROUTER_MODELS_URL, headers)
    models = data.get("data") or data.get("models") or []
    free_ids = sorted({m.get("id") for m in models if m.get("id") and is_free_model(m)})
    paid_count = len([1 for m in models if m.get("id") and not is_free_model(m)])
    return free_ids, len(models), paid_count


def update_allowlist(db_path, free_ids, index="0", apply=False, verbose=False):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    row = cur.execute("SELECT id, data FROM config WHERE id=1").fetchone()
    if not row:
        raise RuntimeError("config row not found (id=1)")

    cfg = json.loads(row["data"])
    cfg.setdefault("openai", {})
    cfg["openai"].setdefault("api_configs", {})
    cfg["openai"]["api_configs"].setdefault(index, {})

    target = cfg["openai"]["api_configs"][index]
    target.setdefault("enable", True)
    target.setdefault("connection_type", "external")
    target.setdefault("tags", [])
    target.setdefault("prefix_id", "")

    old_list = target.get("model_ids", [])
    new_list = list(free_ids)

    if verbose:
        print(f"[i] existing allowlist: {len(old_list)}")
        print(f"[i] new allowlist     : {len(new_list)}")
        if new_list:
            print(f"[i] first 10 IDs     : {new_list[:10]}")

    if not apply:
        return False

    target["model_ids"] = new_list
    cur.execute(
        "UPDATE config SET data=?, updated_at=CURRENT_TIMESTAMP WHERE id=1",
        (json.dumps(cfg, ensure_ascii=False),),
    )
    conn.commit()
    conn.close()
    return True


def main():
    ap = argparse.ArgumentParser(description="Write only-free OpenRouter IDs into OpenWebUI allowlist.")
    ap.add_argument("--db", required=True, help="Path to webui.db (e.g. /opt/open-webui/backend/data/webui.db)")
    ap.add_argument("--config-index", default="0", help="Which openai.api_configs index to write (default: 0)")
    ap.add_argument("--apply", action="store_true", help="Write changes (otherwise dry-run)")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        print("ERROR: Set OPENROUTER_API_KEY environment variable.", file=sys.stderr)
        sys.exit(1)

    free_ids, total, paid = fetch_free_ids(api_key)
    free = len(free_ids)

    print(f"OpenRouter models: {total}  |  FREE: {free}  |  PAID: {paid}")
    if args.verbose and free_ids:
        print(f"[i] sample FREE IDs: {free_ids[:10]}")

    changed = update_allowlist(
        db_path=args.db,
        free_ids=free_ids,
        index=args.config_index,
        apply=args.apply,
        verbose=args.verbose,
    )

    if args.apply:
        print("✅ Allowlist updated with FREE models only.")
    else:
        print("\n(dry-run; use --apply to write)")


if __name__ == "__main__":
    main()
