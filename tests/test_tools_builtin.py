"""Tests for the built-in tools.

All tools now execute locally (no Docker dependency).
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

from src.tools.builtin import (
    BashTool,
    PythonExecTool,
    ReadFileTool,
    WebFetchTool,
    WriteFileTool,
)


class TestReadFileTool:
    """Tests do NOT require Docker."""
    async def test_read_existing_file(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("hello world")
            tmp = f.name
        try:
            tool = ReadFileTool()
            result = await tool.execute(file_path=tmp)
            assert result.success is True
            assert result.output == "hello world"
        finally:
            os.unlink(tmp)

    async def test_file_not_found(self) -> None:
        tool = ReadFileTool()
        result = await tool.execute(file_path="/tmp/nonexistent_file_12345.txt")
        assert result.success is False
        assert "not found" in result.error.lower()

    async def test_empty_path(self) -> None:
        tool = ReadFileTool()
        result = await tool.execute(file_path="")
        assert result.success is False

    async def test_path_traversal_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tool = ReadFileTool(allowed_root=tmpdir)
            result = await tool.execute(file_path="/etc/passwd")
            assert result.success is False
            assert "Permission denied" in result.error or "outside" in result.error


class TestWriteFileTool:
    """Tests do NOT require Docker."""
    async def test_write_and_read_back(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.txt"
            tool = WriteFileTool()
            result = await tool.execute(file_path=str(path), content="written content")
            assert result.success is True
            assert path.read_text() == "written content"

    async def test_creates_parent_directories(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "a" / "b" / "c" / "deep.txt"
            tool = WriteFileTool()
            result = await tool.execute(file_path=str(path), content="deep")
            assert result.success is True
            assert path.read_text() == "deep"

    async def test_path_traversal_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tool = WriteFileTool(allowed_root=tmpdir)
            result = await tool.execute(
                file_path=str(Path(tmpdir) / ".." / "escape.txt"),
                content="should not write",
            )
            assert result.success is False
            assert "Permission denied" in result.error

    async def test_empty_path(self) -> None:
        tool = WriteFileTool()
        result = await tool.execute(file_path="", content="x")
        assert result.success is False


_IS_WINDOWS = os.name == "nt"


@pytest.mark.skipif(_IS_WINDOWS, reason="BashTool requires a POSIX shell")
class TestBashTool:
    """Tests run locally (no Docker required)."""

    async def test_echo_command(self) -> None:
        tool = BashTool()
        result = await tool.execute(command='echo "hello from bash"')
        assert result.success is True
        assert "hello from bash" in result.output

    async def test_failing_command(self) -> None:
        tool = BashTool()
        result = await tool.execute(command="exit 42")
        assert result.success is False
        assert "42" in result.error

    async def test_empty_command(self) -> None:
        tool = BashTool()
        result = await tool.execute(command="")
        assert result.success is False
        assert "command is required" in result.error

    async def test_timeout_kills_command(self) -> None:
        tool = BashTool(timeout=0.5)
        result = await tool.execute(command="sleep 10")
        assert result.success is False
        assert "timed out" in result.error.lower()


class TestPythonExecTool:
    """Tests run locally (no Docker required)."""

    async def test_simple_code(self) -> None:
        tool = PythonExecTool()
        result = await tool.execute(code='print("hello from python")')
        assert result.success is True
        assert "hello from python" in result.output

    async def test_code_with_result(self) -> None:
        tool = PythonExecTool()
        result = await tool.execute(code="print(sum(range(10)))")
        assert result.success is True
        assert "45" in result.output

    async def test_error_code(self) -> None:
        tool = PythonExecTool()
        result = await tool.execute(code="raise ValueError('boom')")
        assert result.success is False

    async def test_empty_code(self) -> None:
        tool = PythonExecTool()
        result = await tool.execute(code="")
        assert result.success is False
        assert "code is required" in result.error


class TestWebFetchTool:
    async def test_invalid_url_scheme(self) -> None:
        tool = WebFetchTool()
        result = await tool.execute(url="ftp://example.com")
        assert result.success is False
        assert "Only http/https" in result.error

    async def test_empty_url(self) -> None:
        tool = WebFetchTool()
        result = await tool.execute(url="")
        assert result.success is False
        assert "url is required" in result.error
