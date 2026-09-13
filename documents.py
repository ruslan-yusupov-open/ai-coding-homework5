"""Read-only access to a small, public Markdown knowledge base."""

import os
import stat
from pathlib import Path, PureWindowsPath

MAX_BYTES = 128 * 1024
MAX_DOCS = 200
MAX_ENTRIES = 1000


class DocumentError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


def is_link(path: Path) -> bool:
    info = path.lstat()
    return path.is_symlink() or bool(
        getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
    )


class Documents:
    def __init__(self, root: Path):
        self.root = root.absolute()

    def check_root(self) -> None:
        if is_link(self.root) or not self.root.is_dir():
            raise DocumentError("ACCESS_DENIED", "Knowledge root must be a regular directory.")

    def resolve(self, relative: str) -> Path:
        self.check_root()
        parts = relative.replace("\\", "/").split("/")
        if (
            PureWindowsPath(relative).drive
            or any(not p or p.startswith(".") or ":" in p for p in parts)
            or "\x00" in relative
        ):
            raise DocumentError("ACCESS_DENIED", "Use a relative Markdown path inside knowledge.")
        path = self.root
        for part in parts:
            path = path / part
            if is_link(path):
                raise DocumentError("ACCESS_DENIED", "Links and junctions are not allowed.")
        if not path.resolve().is_relative_to(self.root.resolve()):
            raise DocumentError("ACCESS_DENIED", "Path is outside knowledge.")
        if path.suffix.lower() != ".md" or not path.is_file():
            raise DocumentError("ACCESS_DENIED", "Only regular Markdown files are allowed.")
        return path

    def read(self, relative: str) -> str:
        path = self.resolve(relative)
        # Bound the read even if a file grows between stat and open.
        with path.open("rb") as stream:
            raw = stream.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise DocumentError("LIMIT_EXCEEDED", "Document exceeds 128 KiB.")
        try:
            return raw.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise DocumentError("INVALID_ENCODING", "Document must use UTF-8.") from exc

    def paths(self) -> list[str]:
        self.check_root()
        found = []
        visited = 0
        pending = [self.root]
        while pending:
            directory = pending.pop()
            with os.scandir(directory) as entries:
                for entry in entries:
                    visited += 1
                    if visited > MAX_ENTRIES:
                        raise DocumentError("LIMIT_EXCEEDED", "Knowledge exceeds 1000 entries.")
                    path = Path(entry.path)
                    if entry.name.startswith(".") or is_link(path):
                        continue
                    if entry.is_dir(follow_symlinks=False):
                        pending.append(path)
                    elif entry.is_file(follow_symlinks=False) and path.suffix.lower() == ".md":
                        found.append(path.relative_to(self.root).as_posix())
                        if len(found) > MAX_DOCS:
                            raise DocumentError(
                                "LIMIT_EXCEEDED", "Knowledge exceeds 200 documents."
                            )
        return sorted(found)

    def list_docs(self) -> dict:
        items = []
        for path in self.paths():
            lines = self.read(path).splitlines()
            title = next((line[2:].strip() for line in lines if line.startswith("# ")), path)
            items.append({"path": path, "title": title[:300], "lines": len(lines)})
        return {"documents": items, "count": len(items)}

    def search_docs(self, query: str, limit: int) -> dict:
        matches = []
        needle = query.casefold()
        for path in self.paths():
            for number, line in enumerate(self.read(path).splitlines(), 1):
                if needle in line.casefold():
                    if len(matches) == limit:
                        return {"matches": matches, "count": len(matches), "truncated": True}
                    matches.append({"path": path, "line": number, "snippet": line[:300]})
        return {"matches": matches, "count": len(matches), "truncated": False}

    def get_doc(self, path: str) -> dict:
        content = self.read(path)
        return {
            "path": path.replace("\\", "/"),
            "content": content,
            "lines": len(content.splitlines()),
        }
