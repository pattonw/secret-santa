import datetime
import json
from pathlib import Path
import base64

from cryptography.fernet import Fernet
import hashlib


def store_assignments(directory, assignments, key=None):
    now = datetime.datetime.now()
    history_dir = Path(directory, "history")
    if not history_dir.exists():
        history_dir.mkdir(parents=True)
    history_file = history_dir / f"{now.year}.json"
    if history_file.exists():
        raise FileExistsError(
            f"Assignments already exist for year {now.year}!"
            f"To create new assignments please delete {history_file} first."
        )

    write_assignments(history_file, assignments, key)

def write_assignments(history_file, assignments, key=None):
    if key is None:
        with history_file.open("w") as f:
            f.write(json.dumps(assignments))
    else:
        m = hashlib.sha256()
        m.update(key)
        key = base64.urlsafe_b64encode(m.digest())
        fernet = Fernet(key)
        encrypted = [
            (k, fernet.encrypt(v.encode()).decode("utf-8")) for k, v in assignments
        ]
        for a, b in encrypted:
            c = fernet.decrypt(bytes(b, "utf-8"))
        with history_file.open("w") as f:
            f.write(json.dumps(encrypted))


def load(file, key=None):
    raw = json.loads(file.open().read())
    if key is None:
        return raw
    else:

        m = hashlib.sha256()
        m.update(key)
        key = base64.urlsafe_b64encode(m.digest())
        fernet = Fernet(key)
        decoded = [(a, fernet.decrypt(bytes(b, "utf-8")).decode("utf-8")) for a, b in raw]
        return decoded


def read_assignments(directory, history=True, key=None):
    history_dir = Path(directory, "history")
    if not history_dir.exists():
        history_dir.mkdir(parents=True)
    if history:
        historical_assignments = {
            history_file.name[:-5]: load(history_file, key=key)
            for history_file in history_dir.iterdir()
        }
        return historical_assignments
    else:
        year = datetime.datetime.now().year
        try:
            assignments = load((history_dir / f"{year}.json"), key=key)
            return assignments
        except FileNotFoundError as e:
            raise ValueError(
                f"Assignments have not yet been created for {year}! "
                f"Please run `new-assignments --save`"
            ) from e
