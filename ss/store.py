"""Persist assignments.  Giftees are encrypted at rest so the organizer can
take part without seeing who gives to whom.

The key is read from ``<config-dir>/secret.key``.  Older config directories
without that file fall back to the text of ``config.yaml`` as the key, which
is what previous versions did; ``secret-santa <dir> rekey`` migrates them.
"""

from __future__ import annotations

import base64
import datetime
import hashlib
import json
import secrets
from pathlib import Path

from cryptography.fernet import Fernet

KEY_FILE = "secret.key"


def current_year() -> int:
    return datetime.date.today().year


def legacy_key(directory) -> bytes:
    return (Path(directory) / "config.yaml").read_bytes()


def has_key_file(directory) -> bool:
    return (Path(directory) / KEY_FILE).exists()


def load_key(directory) -> bytes:
    key_file = Path(directory) / KEY_FILE
    if key_file.exists():
        return key_file.read_bytes().strip()
    return legacy_key(directory)


def generate_key() -> bytes:
    return secrets.token_urlsafe(48).encode()


def _fernet(key: bytes) -> Fernet:
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(key).digest()))


def write_assignments(file_path: Path, assignments, key: bytes | None = None):
    pairs = [[a, b] for a, b in assignments]
    if key is not None:
        fernet = _fernet(key)
        pairs = [[a, fernet.encrypt(b.encode()).decode("utf-8")] for a, b in pairs]
    Path(file_path).write_text(json.dumps(pairs))


def load(file: Path, key: bytes | None = None) -> list[tuple[str, str]]:
    raw = json.loads(Path(file).read_text())
    if key is None:
        return [(a, b) for a, b in raw]
    fernet = _fernet(key)
    return [(a, fernet.decrypt(b.encode("utf-8")).decode("utf-8")) for a, b in raw]


def history_dir(directory) -> Path:
    path = Path(directory) / "history"
    path.mkdir(parents=True, exist_ok=True)
    return path


def history_files(directory) -> list[Path]:
    return sorted(history_dir(directory).glob("*.json"))


def store_assignments(directory, assignments, key=None, year: int | None = None):
    year = year or current_year()
    history_file = history_dir(directory) / f"{year}.json"
    if history_file.exists():
        raise FileExistsError(
            f"Assignments already exist for year {year}! "
            f"To create new assignments please delete {history_file} first."
        )
    write_assignments(history_file, assignments, key)
    return history_file


def read_assignments(directory, history=True, key=None, year: int | None = None):
    if history:
        return {f.stem: load(f, key=key) for f in history_files(directory)}
    year = year or current_year()
    history_file = history_dir(directory) / f"{year}.json"
    if not history_file.exists():
        raise ValueError(
            f"Assignments have not yet been created for {year}! "
            f"Please run `new-assignments --save`"
        )
    return load(history_file, key=key)


def rekey(directory, old_key: bytes | None, new_key: bytes | None) -> list[Path]:
    """Re-encode every history file from ``old_key`` to ``new_key``.
    Everything is decoded first so a bad old key fails before any writes."""
    files = history_files(directory)
    decoded = [(f, load(f, key=old_key)) for f in files]
    for f, pairs in decoded:
        write_assignments(f, pairs, key=new_key)
    return files
