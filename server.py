"""
colab-mcp: MCP server for reading/writing Google Colab notebooks via Drive API.
Phase 1 — file-level operations (no live kernel).
Phase 2 — Chrome extension bridge for live cell execution (planned).
"""

import json
import os
from pathlib import Path
from typing import Any

import nbformat
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import io

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

SCOPES = ["https://www.googleapis.com/auth/drive"]
TOKEN_PATH = Path("~/.colab_mcp_token.json").expanduser()
CREDS_PATH = Path("credentials.json")

app = Server("colab-mcp")


def get_drive_service():
    creds = None
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDS_PATH, SCOPES)
            creds = flow.run_local_server(port=0)
        TOKEN_PATH.write_text(creds.to_json())
    return build("drive", "v3", credentials=creds)


def download_notebook(service, file_id: str) -> nbformat.NotebookNode:
    request = service.files().get_media(fileId=file_id)
    buf = io.BytesIO()
    downloader = MediaIoBaseDownload(buf, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    buf.seek(0)
    return nbformat.read(buf, as_version=4)


def upload_notebook(service, file_id: str, nb: nbformat.NotebookNode):
    buf = io.BytesIO()
    nbformat.write(nb, io.TextIOWrapper(buf, encoding="utf-8"))
    buf.seek(0)
    media = MediaIoBaseUpload(buf, mimetype="application/json")
    service.files().update(fileId=file_id, media_body=media).execute()


def find_notebook_id(service, name: str) -> str | None:
    """find notebook by name in Drive, return file_id or None"""
    q = f"name='{name}' and mimeType='application/vnd.google.colaboratory'"
    results = service.files().list(q=q, fields="files(id,name)").execute()
    files = results.get("files", [])
    return files[0]["id"] if files else None


@app.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="list_notebooks",
            description="list Colab notebooks in Google Drive",
            inputSchema={"type": "object", "properties": {
                "query": {"type": "string", "description": "optional name filter"}
            }},
        ),
        types.Tool(
            name="read_notebook",
            description="read all cells from a Colab notebook",
            inputSchema={"type": "object", "required": ["file_id"], "properties": {
                "file_id": {"type": "string"}
            }},
        ),
        types.Tool(
            name="get_cell",
            description="get source of a single cell by index",
            inputSchema={"type": "object", "required": ["file_id", "index"], "properties": {
                "file_id": {"type": "string"},
                "index": {"type": "integer"}
            }},
        ),
        types.Tool(
            name="add_cell",
            description="add a new cell at given index (or end if omitted)",
            inputSchema={"type": "object", "required": ["file_id", "source"], "properties": {
                "file_id": {"type": "string"},
                "source": {"type": "string"},
                "cell_type": {"type": "string", "enum": ["code", "markdown"], "default": "code"},
                "index": {"type": "integer", "description": "insert position, default appends"}
            }},
        ),
        types.Tool(
            name="edit_cell",
            description="overwrite source of a cell by index",
            inputSchema={"type": "object", "required": ["file_id", "index", "source"], "properties": {
                "file_id": {"type": "string"},
                "index": {"type": "integer"},
                "source": {"type": "string"}
            }},
        ),
        types.Tool(
            name="delete_cell",
            description="delete a cell by index",
            inputSchema={"type": "object", "required": ["file_id", "index"], "properties": {
                "file_id": {"type": "string"},
                "index": {"type": "integer"}
            }},
        ),
        types.Tool(
            name="move_cell",
            description="move a cell from one index to another",
            inputSchema={"type": "object", "required": ["file_id", "from_index", "to_index"], "properties": {
                "file_id": {"type": "string"},
                "from_index": {"type": "integer"},
                "to_index": {"type": "integer"}
            }},
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[types.TextContent]:
    service = get_drive_service()

    if name == "list_notebooks":
        q = "mimeType='application/vnd.google.colaboratory'"
        if arguments.get("query"):
            q += f" and name contains '{arguments['query']}'"
        results = service.files().list(q=q, fields="files(id,name,modifiedTime)").execute()
        files = results.get("files", [])
        text = "\n".join(f"{f['name']} | {f['id']} | modified: {f['modifiedTime']}" for f in files)
        return [types.TextContent(type="text", text=text or "no notebooks found")]

    if name == "read_notebook":
        nb = download_notebook(service, arguments["file_id"])
        lines = []
        for i, cell in enumerate(nb.cells):
            lines.append(f"[{i}] {cell.cell_type}\n{cell.source}\n")
        return [types.TextContent(type="text", text="\n".join(lines))]

    if name == "get_cell":
        nb = download_notebook(service, arguments["file_id"])
        idx = arguments["index"]
        cell = nb.cells[idx]
        return [types.TextContent(type="text", text=f"[{idx}] {cell.cell_type}\n{cell.source}")]

    if name == "add_cell":
        nb = download_notebook(service, arguments["file_id"])
        cell_type = arguments.get("cell_type", "code")
        source = arguments["source"]
        if cell_type == "code":
            new_cell = nbformat.v4.new_code_cell(source=source)
        else:
            new_cell = nbformat.v4.new_markdown_cell(source=source)
        idx = arguments.get("index")
        if idx is None:
            nb.cells.append(new_cell)
        else:
            nb.cells.insert(idx, new_cell)
        upload_notebook(service, arguments["file_id"], nb)
        return [types.TextContent(type="text", text=f"cell added at index {idx if idx is not None else len(nb.cells)-1}")]

    if name == "edit_cell":
        nb = download_notebook(service, arguments["file_id"])
        nb.cells[arguments["index"]].source = arguments["source"]
        upload_notebook(service, arguments["file_id"], nb)
        return [types.TextContent(type="text", text=f"cell {arguments['index']} updated")]

    if name == "delete_cell":
        nb = download_notebook(service, arguments["file_id"])
        nb.cells.pop(arguments["index"])
        upload_notebook(service, arguments["file_id"], nb)
        return [types.TextContent(type="text", text=f"cell {arguments['index']} deleted")]

    if name == "move_cell":
        nb = download_notebook(service, arguments["file_id"])
        cell = nb.cells.pop(arguments["from_index"])
        nb.cells.insert(arguments["to_index"], cell)
        upload_notebook(service, arguments["file_id"], nb)
        return [types.TextContent(type="text", text=f"cell moved {arguments['from_index']} -> {arguments['to_index']}")]

    return [types.TextContent(type="text", text=f"unknown tool: {name}")]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
