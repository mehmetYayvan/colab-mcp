"""unit tests for server.py — mocks Drive API and bridge, no real network/Colab needed"""

import threading
import time
from unittest.mock import MagicMock, patch

import nbformat
import pytest

import server


def make_nb(sources):
    nb = nbformat.v4.new_notebook()
    for s in sources:
        nb.cells.append(nbformat.v4.new_code_cell(source=s))
    return nb


@pytest.fixture
def mock_nb(monkeypatch):
    nb = make_nb(["a=1", "b=2", "c=3"])
    monkeypatch.setattr(server, "get_drive_service", lambda: MagicMock())
    monkeypatch.setattr(server, "download_notebook", lambda service, file_id: nb)
    uploaded = {}
    def fake_upload(service, file_id, nb_arg):
        uploaded["nb"] = nb_arg
    monkeypatch.setattr(server, "upload_notebook", fake_upload)
    return nb, uploaded


async def call(name, **kwargs):
    return await server.call_tool(name, kwargs)


@pytest.mark.asyncio
async def test_read_notebook(mock_nb):
    result = await call("read_notebook", file_id="f1")
    text = result[0].text
    assert "[0] code\na=1" in text
    assert "[2] code\nc=3" in text


@pytest.mark.asyncio
async def test_get_cell(mock_nb):
    result = await call("get_cell", file_id="f1", index=1)
    assert result[0].text == "[1] code\nb=2"


@pytest.mark.asyncio
async def test_add_cell_appends(mock_nb):
    nb, uploaded = mock_nb
    result = await call("add_cell", file_id="f1", source="d=4")
    assert "index 3" in result[0].text
    assert uploaded["nb"].cells[3].source == "d=4"


@pytest.mark.asyncio
async def test_add_cell_inserts_at_index(mock_nb):
    nb, uploaded = mock_nb
    await call("add_cell", file_id="f1", source="x=0", index=1)
    cells = uploaded["nb"].cells
    assert [c.source for c in cells] == ["a=1", "x=0", "b=2", "c=3"]


@pytest.mark.asyncio
async def test_edit_cell(mock_nb):
    nb, uploaded = mock_nb
    result = await call("edit_cell", file_id="f1", index=1, source="b=99")
    assert "cell 1 updated" in result[0].text
    assert uploaded["nb"].cells[1].source == "b=99"


@pytest.mark.asyncio
async def test_delete_cell(mock_nb):
    nb, uploaded = mock_nb
    result = await call("delete_cell", file_id="f1", index=1)
    assert "cell 1 deleted" in result[0].text
    assert [c.source for c in uploaded["nb"].cells] == ["a=1", "c=3"]


@pytest.mark.asyncio
async def test_move_cell(mock_nb):
    nb, uploaded = mock_nb
    result = await call("move_cell", file_id="f1", from_index=0, to_index=2)
    assert "moved 0 -> 2" in result[0].text
    assert [c.source for c in uploaded["nb"].cells] == ["b=2", "c=3", "a=1"]


@pytest.mark.asyncio
async def test_list_notebooks(monkeypatch):
    fake_service = MagicMock()
    fake_service.files.return_value.list.return_value.execute.return_value = {
        "files": [{"name": "nb1", "id": "id1", "modifiedTime": "t1"}]
    }
    monkeypatch.setattr(server, "get_drive_service", lambda: fake_service)
    result = await call("list_notebooks")
    assert "nb1 | id1 | modified: t1" in result[0].text


@pytest.mark.asyncio
async def test_list_notebooks_empty(monkeypatch):
    fake_service = MagicMock()
    fake_service.files.return_value.list.return_value.execute.return_value = {"files": []}
    monkeypatch.setattr(server, "get_drive_service", lambda: fake_service)
    result = await call("list_notebooks")
    assert result[0].text == "no notebooks found"


@pytest.mark.asyncio
async def test_unknown_tool(mock_nb):
    result = await call("bogus_tool", file_id="f1")
    assert "unknown tool" in result[0].text


@pytest.fixture(autouse=True)
def drain_bridge_queue():
    """clear leftover commands from prior tests so fake_extension doesn't pick up stale ids"""
    while not server._cmd_queue.empty():
        server._cmd_queue.get_nowait()
    yield


def _fake_extension(response: dict, attempts: int = 50):
    for _ in range(attempts):
        if not server._cmd_queue.empty():
            cmd = server._cmd_queue.get()
            cmd_id = cmd["id"]
            if cmd_id in server._pending:
                server._results[cmd_id] = response
                server._pending[cmd_id].set()
                return
        time.sleep(0.05)


@pytest.mark.asyncio
async def test_run_cell_timeout(monkeypatch):
    result = await call("run_cell", index=0, timeout=1)
    assert "no response from extension" in result[0].text


@pytest.mark.asyncio
async def test_run_cell_success():
    threading.Thread(target=_fake_extension, args=({"output": "42"},), daemon=True).start()
    result = await server.call_tool("run_cell", {"index": 0, "timeout": 5})
    assert result[0].text == "42"


@pytest.mark.asyncio
async def test_get_output_error():
    threading.Thread(target=_fake_extension, args=({"error": "cell not found"},), daemon=True).start()
    result = await server.call_tool("get_output", {"index": 9})
    assert "error: cell not found" in result[0].text
