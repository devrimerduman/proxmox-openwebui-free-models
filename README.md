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
- An OpenRouter API key

## Installation
Clone the repository:

```bash
git clone https://github.com/yourusername/proxmox-openwebui-free-models.git
cd proxmox-openwebui-free-models
chmod +x proxmox_openwebui_free_models.py
