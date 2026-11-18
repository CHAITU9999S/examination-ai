
import random
from collections import deque
from math import isfinite


def generate_paper(
    question_ids,
    student_id,
    exam_id,
    number_of_questions,
    question_details=None,
    difficulty_counts=None,
    question_type_counts=None,
    randomize=True,
):
    """Generate a deterministic question paper for a student and exam."""

    # Validate requested question count.
    if (
        isinstance(number_of_questions, bool)
        or not isinstance(number_of_questions, int)
        or number_of_questions <= 0
    ):
        raise ValueError("Number of questions must be a positive integer")

    if not isinstance(question_ids, (list, tuple)):
        raise ValueError("Question IDs must be a list or tuple")

    selected = list(question_ids)

    if len(selected) != len(set(selected)):
        raise ValueError("Duplicate question IDs are not allowed")

    if number_of_questions > len(selected):
        raise ValueError("Not enough questions available")

    if not isinstance(randomize, bool):
        raise ValueError("Randomize must be a Boolean value")

    seed = f"{exam_id}-{student_id}"
    rng = random.Random(seed)

    # Preserve existing behavior when distributions are not configured.
    if not difficulty_counts and not question_type_counts:
        if randomize:
            rng.shuffle(selected)

        return selected[:number_of_questions]

    if not isinstance(question_details, dict):
        raise ValueError(
            "Question details are required for distribution-based selection"
        )

    if not isinstance(difficulty_counts, dict) or not isinstance(
        question_type_counts, dict
    ):
        raise ValueError("Both distributions must be dictionaries")

    if not difficulty_counts or not question_type_counts:
        raise ValueError(
            "Both difficulty and question-type distributions are required"
        )

    # Validate distribution values.
    for distribution_name, distribution in (
        ("Difficulty", difficulty_counts),
        ("Question-type", question_type_counts),
    ):
        for count in distribution.values():
            if (
                isinstance(count, bool)
                or not isinstance(count, int)
                or count < 0
            ):
                raise ValueError(
                    f"{distribution_name} counts must be non-negative integers"
                )

        if sum(distribution.values()) != number_of_questions:
            raise ValueError(
                f"{distribution_name} counts must equal "
                "the requested question count"
            )

    difficulties = list(difficulty_counts)
    question_types = list(question_type_counts)

    # Normalize enum values and group available questions.
    groups = {}

    for question_id in selected:
        details = question_details.get(question_id)

        if not isinstance(details, dict):
            continue

        difficulty = details.get("difficulty")
        question_type = details.get("question_type")

        difficulty = getattr(difficulty, "value", difficulty)
        question_type = getattr(question_type, "value", question_type)

        if difficulty not in difficulty_counts:
            continue

        if question_type not in question_type_counts:
            continue

        groups.setdefault(
            (difficulty, question_type), []
        ).append(question_id)

    # Randomize questions within each group.
    for group in groups.values():
        if randomize:
            rng.shuffle(group)

    # Build a maximum-flow network.
    source = "source"
    sink = "sink"
    graph = {}

    def add_edge(start, end, capacity):
        graph.setdefault(start, {})
        graph.setdefault(end, {})

        graph[start][end] = capacity
        graph[end][start] = 0

    # Source -> difficulty nodes.
    for difficulty in difficulties:
        add_edge(
            source,
            ("difficulty", difficulty),
            difficulty_counts[difficulty],
        )

    # Question-type nodes -> sink.
    for question_type in question_types:
        add_edge(
            ("type", question_type),
            sink,
            question_type_counts[question_type],
        )

    # Difficulty nodes -> question-type nodes.
    for difficulty in difficulties:
        for question_type in question_types:
            available = len(
                groups.get((difficulty, question_type), [])
            )

            add_edge(
                ("difficulty", difficulty),
                ("type", question_type),
                available,
            )

    # Edmonds-Karp maximum-flow algorithm.
    total_flow = 0

    while True:
        parent = {source: None}
        queue = deque([source])

        while queue and sink not in parent:
            current = queue.popleft()
            neighbors = list(graph[current])

            if randomize:
                rng.shuffle(neighbors)

            for neighbor in neighbors:
                if (
                    neighbor not in parent
                    and graph[current][neighbor] > 0
                ):
                    parent[neighbor] = current
                    queue.append(neighbor)

                    if neighbor == sink:
                        break

        if sink not in parent:
            break

        flow = float("inf")
        current = sink

        while current != source:
            previous = parent[current]
            flow = min(
                flow,
                graph[previous][current],
            )
            current = previous

        current = sink

        while current != source:
            previous = parent[current]

            graph[previous][current] -= flow
            graph[current][previous] += flow

            current = previous

        total_flow += flow

    if total_flow != number_of_questions:
        raise ValueError(
            "Available questions cannot satisfy the configured distributions"
        )

    # Extract selected questions from the final flow.
    paper = []

    for difficulty in difficulties:
        difficulty_node = ("difficulty", difficulty)

        for question_type in question_types:
            type_node = ("type", question_type)

            selected_count = graph[type_node][difficulty_node]

            if selected_count <= 0:
                continue

            available_questions = groups.get(
                (difficulty, question_type), []
            )

            paper.extend(
                available_questions[:selected_count]
            )

    if len(paper) != number_of_questions:
        raise ValueError(
            "Unable to generate the requested question paper"
        )

    if randomize:
        rng.shuffle(paper)

    return paper
        
