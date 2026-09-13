import os

import pytest

from documents import MAX_BYTES, DocumentError, Documents


@pytest.fixture
def docs(tmp_path):
    root = tmp_path / "knowledge"
    root.mkdir()
    (root / "one.md").write_text("# Один\nБезопасность MCP\n", encoding="utf-8")
    (root / "two.md").write_text("# Two\nMCP setup\nMCP tools\n", encoding="utf-8")
    return Documents(root)


def test_search_returns_cyrillic_lines_and_truthful_truncation(docs):
    result = docs.search_docs("БЕЗОПАСНОСТЬ", 10)
    assert result["matches"] == [{"path": "one.md", "line": 2, "snippet": "Безопасность MCP"}]
    assert docs.search_docs("MCP", 2)["truncated"] is True
    assert docs.search_docs("MCP", 3)["truncated"] is False
    assert docs.search_docs("no-such-term", 10)["count"] == 0


@pytest.mark.parametrize(
    "path",
    [
        "../README.md",
        "/etc/passwd",
        "C:\\secret.md",
        "\\\\host\\share\\file.md",
        "one.md:secret",
        ".hidden.md",
        "folder/../one.md",
        "one.md\x00",
    ],
)
def test_rejects_unsafe_paths(docs, path):
    with pytest.raises(DocumentError, match="relative Markdown"):
        docs.read(path)


def test_non_markdown_and_size_and_encoding(docs):
    (docs.root / "secret.txt").write_text("private")
    with pytest.raises(DocumentError, match="Markdown"):
        docs.read("secret.txt")
    (docs.root / "huge.md").write_bytes(b"x" * (MAX_BYTES + 1))
    with pytest.raises(DocumentError, match="128 KiB"):
        docs.read("huge.md")
    (docs.root / "bad.md").write_bytes(b"\xff")
    with pytest.raises(DocumentError, match="UTF-8"):
        docs.read("bad.md")


def test_symlink_cannot_escape(docs, tmp_path):
    outside = tmp_path / "outside.md"
    outside.write_text("private")
    link = docs.root / "link.md"
    try:
        link.symlink_to(outside)
    except OSError as exc:
        pytest.skip(f"OS does not permit creation of test symlinks: {exc}")
    assert "link.md" not in docs.paths()
    with pytest.raises(DocumentError, match="Links"):
        docs.read("link.md")


@pytest.mark.skipif(os.name != "nt", reason="Windows junction test")
def test_junction_cannot_escape(docs, tmp_path):
    import _winapi

    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "private.md").write_text("private")
    junction = docs.root / "linked"
    _winapi.CreateJunction(str(outside), str(junction))
    try:
        assert docs.paths() == ["one.md", "two.md"]
        with pytest.raises(DocumentError, match="Links"):
            docs.read("linked/private.md")
    finally:
        junction.rmdir()


def test_limits_tree_size(docs, monkeypatch):
    monkeypatch.setattr("documents.MAX_ENTRIES", 1)
    with pytest.raises(DocumentError, match="entries"):
        docs.paths()


def test_log_redaction():
    from server import safe_params

    result = safe_params({"query": "token=example-secret", "password": "hidden", "limit": 2})
    assert result == {"query": "[REDACTED]", "password": "[REDACTED]", "limit": 2}
