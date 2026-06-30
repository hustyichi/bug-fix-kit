from __future__ import annotations

from pathlib import Path


def capture_offsets(log_files: list[Path]) -> dict[str, int]:
    return {str(path): path.stat().st_size if path.exists() else 0 for path in log_files}


def read_since_offsets(offsets: dict[str, int]) -> str:
    chunks: list[str] = []
    for name, offset in offsets.items():
        path = Path(name)
        if not path.exists():
            chunks.append(f"[bfk] missing log file: {name}\n")
            continue
        size = path.stat().st_size
        start = offset if size >= offset else 0
        if size < offset:
            chunks.append(f"[bfk] log file truncated, reading from start: {name}\n")
        with path.open("r", errors="replace") as fh:
            fh.seek(start)
            chunks.append(fh.read())
    return "".join(chunks)
