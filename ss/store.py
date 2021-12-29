import datetime
import json
from pathlib import Path


def store_assignments(directory, assignments):
    now = datetime.datetime.now()
    history_dir = Path(directory, "history")
    if not history_dir.exists():
        history_dir.mkdir(parents=True)
    history_file = history_dir / f"{now.year}"
    if history_file.exists():
        raise FileExistsError(
            f"Assignments already exist for year {now.year}!"
            f"To create new assignments please delete {history_file} first."
        )
    with history_file.open("w") as f:
        f.write(json.dumps(assignments))


def read_assignments(directory, history=True):
    history_dir = Path(directory, "history")
    if not history_dir.exists():
        history_dir.mkdir(parents=True)
    if history:
        historical_assignments = {
            history_file.name: json.loads(history_file.open().read())
            for history_file in history_dir.iterdir()
        }
        return historical_assignments
    else:
        year = datetime.datetime.now().year
        try:
            assignments = json.loads((history_dir / f"{year}").open().read())
            return assignments
        except FileNotFoundError as e:
            raise ValueError(
                f"Assignments have not yet been created for {year}! "
                f"Please run `new-assignments --save`"
            ) from e
