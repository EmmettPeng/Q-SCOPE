from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
from pathlib import Path
from typing import Any


SAFE_ID = re.compile(r"[^A-Za-z0-9._-]+")


def safe_id(value: str, fallback: str = "item") -> str:
    cleaned = SAFE_ID.sub("_", value.strip()).strip("._-")
    return cleaned[:120] or fallback


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_paths(paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths, key=lambda item: item.name):
        digest.update(path.name.encode())
        digest.update(bytes.fromhex(sha256_file(path)))
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    os.replace(temporary, path)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def directory_size(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


def ensure_storage_budget(path: Path, current_output: Path | None = None) -> None:
    from .config import settings

    path.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(path).free < settings.min_free_bytes:
        raise OSError("disk_free_space_below_limit")
    if current_output and directory_size(current_output) > settings.max_run_output_bytes:
        raise OSError("run_output_size_exceeded")
