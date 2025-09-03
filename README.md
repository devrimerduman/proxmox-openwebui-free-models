# Proxmox OpenWebUI Free Models

Ensure that **only free models from [OpenRouter](https://openrouter.ai/)** are selectable in [OpenWebUI](https://github.com/open-webui/open-webui) by writing an allow-list (whitelist) to the OpenWebUI config database.  
Paid models are excluded from the connection's model list. When OpenRouter adds new models, re-run to keep the allow-list up to date.

> **Why allow-list?**  
> Recent OpenWebUI builds populate the Models page dynamically from providers and do not persist per-model toggle states in a dedicated table. The reliable way to enforce “free-only” is an allow-list under `openai.api_configs.*.model_ids` inside the `config` table JSON.

## Features
- Fetches the latest model catalog from OpenRouter API
- Classifies models as **free** vs **paid** (by ID patterns and `pricing`)
- Updates the OpenWebUI SQLite DB (`config.data` JSON) to allow only free models
- Dry-run mode for safety; backs up DB recommended

## Requirements
- Python 3.7+
- `sqlite3`
- An **OpenRouter API key** (Dashboard → API Keys)

## Where is the DB?
Typical path in LXC with native backend:
```
/opt/open-webui/backend/data/webui.db
```

## Quick Start (one-time run on your LXC)

```bash
# 0) Enter the LXC where OpenWebUI runs
pct enter <LXC_ID>     # e.g. pct enter 101

# 1) Install tools
apt update && apt install -y python3 sqlite3

# 2) Backup DB (recommended)
DB=/opt/open-webui/backend/data/webui.db
cp -a "$DB" "${DB}.bak-$(date +%F-%H%M)"

# 3) Set API key for this shell
export OPENROUTER_API_KEY="sk-or-v1-xxxxxxxx"

# 4) Dry-run (preview)
python3 proxmox_openwebui_free_models.py --db "$DB" --verbose

# 5) Apply
python3 proxmox_openwebui_free_models.py --db "$DB" --apply --verbose

# 6) Restart service if needed
systemctl restart open-webui 2>/dev/null || docker restart open-webui 2>/dev/null || true
```

## Cron (keep it updated hourly)

```cron
0 * * * * OPENROUTER_API_KEY=sk-or-v1-xxxxxxxx \
python3 /path/to/proxmox_openwebui_free_models.py --db /opt/open-webui/backend/data/webui.db --apply >>/var/log/openwebui-free-only.log 2>&1
```

## Optional: Keep a second "All models" connection
OpenWebUI supports multiple API connections. You can keep:
- **Connection A (All)** → `model_ids: []` (shows everything)
- **Connection B (Free)** → managed by this script (free only)

Switch between them in the UI as needed.

## How it works
1. Calls `GET https://openrouter.ai/api/v1/models`
2. Marks a model as **free** if:
   - Model ID hints like `:free`, `-free`, `(free)` are present **OR**
   - All numeric price fields are `0`/`None`
3. Updates `config.data.openai.api_configs.<index>.model_ids` with free IDs (default index: `0`)

## License
MIT
