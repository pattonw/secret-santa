"""Build secret santa assignments with a small integer program.

Hard constraints:
  * everyone gives exactly one gift and receives exactly one gift
  * nobody gives to themselves or to anyone in their own group
  * no reciprocal pairs (a -> b and b -> a), unless ``allow_reciprocal`` is set

Soft objective: minimise the number of (gifter, giftee) pairs that have
happened in a previous year.  Ties are broken randomly, and the random
noise is scaled so that it can never outweigh a single historical repeat.
"""

from __future__ import annotations

import itertools
import random
from dataclasses import dataclass

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp


def normalize(name: str) -> str:
    return " ".join(str(name).split()).lower()


def display_name(name: str) -> str:
    return " ".join(part.capitalize() for part in normalize(name).split(" "))


@dataclass(frozen=True)
class Participant:
    name: str
    email: str | None
    group: str

    @property
    def display(self) -> str:
        return display_name(self.name)


def participants(config) -> dict[str, Participant]:
    """Flatten the config's groups into a name -> Participant mapping."""
    found: dict[str, Participant] = {}
    for group_name, members in config.groups.items():
        for person in members or []:
            name = normalize(person.name)
            if name in found:
                raise ValueError(
                    f"participant {name!r} appears twice "
                    f"(groups {found[name].group!r} and {group_name!r})"
                )
            found[name] = Participant(name, person.get("email"), str(group_name))
    if len(found) < 2:
        raise ValueError("need at least two participants")
    return found


def emails(config) -> dict[str, str | None]:
    return {p.name: p.email for p in participants(config).values()}


def by_email(config) -> dict[str, str]:
    """email (lower-cased) -> participant name."""
    return {
        p.email.strip().lower(): p.name
        for p in participants(config).values()
        if p.email
    }


def assignment(config, history, seed=None) -> tuple[list[tuple[str, str]], int]:
    """Return ``(pairs, repeats)``: the chosen (gifter, giftee) pairs and how
    many of them repeat an assignment found in ``history``."""
    people = participants(config)
    names = list(people)
    n = len(names)
    allow_reciprocal = bool(config.get("allow_reciprocal", False))

    pairs = [(a, b) for a in names for b in names]
    index = {pair: i for i, pair in enumerate(pairs)}
    rng = random.Random(seed)

    # exactly n variables end up selected, so total noise is < 1 < one repeat
    cost = np.array([rng.random() / n for _ in pairs])
    repeat_penalty = np.zeros(len(pairs))
    for _year, previous in history.items():
        for gifter, giftee in previous:
            i = index.get((normalize(gifter), normalize(giftee)))
            if i is not None:  # people who left no longer have a variable
                repeat_penalty[i] += 1.0
    cost += repeat_penalty

    upper = np.ones(len(pairs))
    for a, b in pairs:
        if a == b or people[a].group == people[b].group:
            upper[index[(a, b)]] = 0.0

    rows, lows, highs = [], [], []
    for person in names:
        gives = np.zeros(len(pairs))
        gets = np.zeros(len(pairs))
        for other in names:
            gives[index[(person, other)]] = 1.0
            gets[index[(other, person)]] = 1.0
        rows += [gives, gets]
        lows += [1.0, 1.0]
        highs += [1.0, 1.0]
    if not allow_reciprocal:
        for a, b in itertools.combinations(names, 2):
            row = np.zeros(len(pairs))
            row[index[(a, b)]] = 1.0
            row[index[(b, a)]] = 1.0
            rows.append(row)
            lows.append(0.0)
            highs.append(1.0)

    result = milp(
        c=cost,
        constraints=LinearConstraint(np.array(rows), lows, highs),
        integrality=np.ones(len(pairs)),
        bounds=Bounds(np.zeros(len(pairs)), upper),
        options={"time_limit": 300},
    )
    if not result.success or result.x is None:
        raise RuntimeError(
            "no feasible assignment exists for this config "
            f"({result.message}). Check the groups and allow_reciprocal."
        )
    chosen = [pairs[i] for i in range(len(pairs)) if result.x[i] > 0.5]
    repeats = int(sum(repeat_penalty[index[p]] > 0 for p in chosen))
    return chosen, repeats
