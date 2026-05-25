# colab-mcp

MCP server that lets Claude read and edit Google Colab notebooks directly via the Drive API.
No more copy-pasting cells. Claude can list, read, add, edit, delete, and move cells.

## Setup

### 1. Install dependencies
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Google Drive credentials
- Go to [Google Cloud Console](https://console.cloud.google.com/)
- Create a project → enable Drive API → create OAuth 2.0 Desktop credentials
- Download as `credentials.json` and place in this directory (it's gitignored)

### 3. Wire into Claude Code
Add to `~/.claude/settings.json` under `mcpServers`:
```json
"colab-mcp": {
  "command": "/path/to/colab-mcp/.venv/bin/python",
  "args": ["/path/to/colab-mcp/server.py"]
}
```

### 4. First run — OAuth flow
Run `python server.py` once manually to complete the browser OAuth flow.
Token is saved to `~/.colab_mcp_token.json`.

## Tools available to Claude
| Tool | Description |
|------|-------------|
| `list_notebooks` | list Colab notebooks in Drive (optional name filter) |
| `read_notebook` | dump all cells with indices |
| `get_cell` | get a single cell by index |
| `add_cell` | insert code or markdown cell at any position |
| `edit_cell` | overwrite a cell's source |
| `delete_cell` | remove a cell |
| `move_cell` | reorder cells |

## Roadmap
- [ ] Phase 2: Chrome extension bridge for live cell execution + output capture
