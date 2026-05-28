# colab-mcp

Control Google Colab notebooks directly from Claude Code. Read cells, edit them, run them, and get output back — no copy-pasting.

## How it works

A local MCP server connects Claude Code to Google Drive (for reading/writing notebooks) and to a Chrome extension (for running cells in an open Colab tab).

```
Claude Code  ←→  MCP server  ←→  Google Drive API  (read/write cells)
                             ←→  Chrome extension  (run cells, get output)
```

## Setup

### 1. Install the MCP server

```bash
git clone https://github.com/mehmetYayvan/colab-mcp
cd colab-mcp
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Google Drive credentials

- [Google Cloud Console](https://console.cloud.google.com) → create project → enable Drive API
- Credentials → OAuth 2.0 Client ID → Desktop app → download JSON
- Save as `credentials.json` in the project root

### 3. Authenticate

```bash
source .venv/bin/activate
python auth.py
```

Completes the OAuth flow and saves a token to `~/.colab_mcp_token.json`.

### 4. Register with Claude Code

```bash
claude mcp add --scope user colab-mcp /path/to/colab-mcp/.venv/bin/python /path/to/colab-mcp/server.py
```

### 5. Install the Chrome extension

- Go to `chrome://extensions` → enable Developer mode → Load unpacked
- Select the `extension/` folder

## Tools

| Tool | Description |
|------|-------------|
| `list_notebooks` | list Colab notebooks in Drive |
| `read_notebook` | read all cells with indices |
| `get_cell` | get a single cell by index |
| `add_cell` | insert a code or markdown cell |
| `edit_cell` | overwrite a cell's source |
| `delete_cell` | remove a cell |
| `move_cell` | reorder cells |
| `run_cell` | execute a cell and return output |
| `get_output` | read current output without running |

## Requirements

- Python 3.10+
- Claude Code CLI
- Google Chrome
- A Google account with Colab access
