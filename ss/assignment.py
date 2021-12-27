from mip import Model, BINARY, minimize, xsum, OptimizationStatus

import itertools
import random
import json


def count(current):
    while True:
        yield (current)
        current += 1


def emails(config):
    participant_emails = {}

    groups = config.groups
    for group_name, g in groups.items():
        for person in g:
            participant_emails.setdefault(person.name, person.email)

    return participant_emails


def assignment(config, history):
    participant_id = count(0)

    participants = {}
    no_match_constraints = []

    groups = config.groups
    for group_name, g in groups.items():
        group_constraints = set()
        for person in g:
            participants.setdefault(person.name, next(participant_id))
            group_constraints.add(person.name)
        no_match_constraints.append(group_constraints)

    pairings = list(itertools.product(participants.keys(), participants.keys()))
    var_ids = {pairing: i for i, pairing in enumerate(pairings)}

    m = Model()
    variables = [m.add_var(var_type=BINARY, name=json.dumps(pair)) for pair in pairings]

    # add no_match_constraings:
    not_allowed = [
        (person_a, person_b)
        for people in no_match_constraints
        for person_a, person_b in itertools.product(people, people)
    ]

    # add no self matching
    not_allowed += [(participant, participant) for participant in participants]

    for match in not_allowed:
        m += variables[var_ids[match]] == 0

    # make sure everyone matches
    for participant in participants:
        participant_gives = []
        for pairing in pairings:
            if participant == pairing[0]:
                participant_gives.append(pairing)
        m += xsum([variables[var_ids[pairing]] for pairing in participant_gives]) == 1

    # make sure everyone get one present
    for patricipant in participants:
        participant_gets = []
        for pairing in pairings:
            if patricipant == pairing[1]:
                participant_gets.append(pairing)
        m += xsum([variables[var_ids[pairing]] for pairing in participant_gets]) == 1

    # make sure if a -> b then b !> a
    for person_a, person_b in itertools.combinations(participants, 2):
        m += (
            variables[var_ids[(person_a, person_b)]]
            + variables[var_ids[(person_b, person_a)]]
            <= 1
        )

    # add random costs to get random pairings
    weights = [random.random() for _ in range(len(variables))]

    # minimize historical overlap
    # simply adds 1 extra weight to any assignment that has been made before
    for date, previous_assignment in history.items():
        for gifter, giftee in previous_assignment:
            var_id = var_ids[(gifter, giftee)]
            weights[var_id] += 1

    m.objective = minimize(
        xsum(variables[i] * weights[i] for i in range(len(variables)))
    )

    m.max_gap = 0.05
    status = m.optimize(max_seconds=300)
    if status == OptimizationStatus.OPTIMAL:
        print("optimal solution cost {} found".format(m.objective_value))
    elif status == OptimizationStatus.FEASIBLE:
        print(
            "sol.cost {} found, best possible: {}".format(
                m.objective_value, m.objective_bound
            )
        )
    elif status == OptimizationStatus.NO_SOLUTION_FOUND:
        print(
            "no feasible solution found, lower bound is: {}".format(m.objective_bound)
        )
    if status == OptimizationStatus.OPTIMAL or status == OptimizationStatus.FEASIBLE:
        for v in m.vars:
            if abs(v.x) > 1e-6:
                yield json.loads(v.name)
