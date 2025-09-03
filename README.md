# Proxmox OpenWebUI Free Models

This script ensures that **only free models from [OpenRouter](https://openrouter.ai/)** remain active inside [OpenWebUI](https://github.com/open-webui/open-webui).  
Paid models are automatically disabled. When OpenRouter adds new models, the script updates the database so only free ones are enabled.

## Features
- Automatically detects free vs. paid models from OpenRouter API
- Updates OpenWebUI SQLite database (`webui.db`)
- Safe: backs up database before changes
- Can run manually or via cron for automation

## Requirements
- Python 3.7+
- `sqlite3`
- An OpenRouter API key (get it from [OpenRouter](https://openrouter.ai))

## Installation
Clone the repository:

```bash
git clone https://github.com/yourusername/proxmox-openwebui-free-models.git
cd proxmox-openwebui-free-models
chmod +x proxmox_openwebui_free_models.py
```

## Usage

### 1. Dry-run (preview changes)
This shows which models would be activated or deactivated without modifying the database:
```bash
OPENROUTER_API_KEY="your_api_key_here" python3 proxmox_openwebui_free_models.py --verbose
```

### 2. Apply changes (update database)
This will actually modify the `webui.db` so only free models remain active:
```bash
OPENROUTER_API_KEY="your_api_key_here" python3 proxmox_openwebui_free_models.py --apply --verbose
```

### 3. Using a custom database path
If your OpenWebUI database is in a non-standard location:
```bash
OPENROUTER_API_KEY="your_api_key_here" python3 proxmox_openwebui_free_models.py --apply --db /app/data/webui.db
```

### 4. Automating with cron
To automatically run the script every hour:

```cron
0 * * * * OPENROUTER_API_KEY=your_api_key_here /path/to/proxmox_openwebui_free_models.py --apply >>/var/log/openwebui-free.log 2>&1
```

This ensures that when OpenRouter releases new models, only free ones are kept active.

## How it Works
1. The script fetches the latest models list from OpenRouter API.
2. It classifies models as **free** if:
   - The model ID contains `:free`, `-free`, `(free)`
   - OR all pricing fields are `0` or `None`
3. It updates the `webui.db` database so only free models are active and visible.

## License
MIT License
