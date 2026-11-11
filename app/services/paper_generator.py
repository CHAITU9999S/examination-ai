
import random


def generate_paper(
    question_ids,
    student_id,
    exam_id,
    number_of_questions,
    question_details=None,
    difficulty_counts=None,
    question_type_counts=None,
    randomize=True
):
    if number_of_questions <= 0:
        raise ValueError("Number of questions must be positive")

    if number_of_questions > len(question_ids):
        raise ValueError("Not enough questions available")

    seed = f"{exam_id}-{student_id}"
    rng = random.Random(seed)

    selected = list(question_ids)

    # Preserve the existing behavior when no distributions are configured.
    if not difficulty_counts and not question_type_counts:
        if randomize:
            rng.shuffle(selected)

        return selected[:number_of_questions]

    if not question_details:
        raise ValueError(
            "Question details are required for distribution-based selection"
        )

    if not difficulty_counts or not question_type_counts:
        raise ValueError(
            "Both difficulty and question-type distributions are required"
        )

    if sum(difficulty_counts.values()) != number_of_questions:
        raise ValueError(
            "Difficulty counts must equal the requested question count"
        )

    if sum(question_type_counts.values()) != number_of_questions:
        raise ValueError(
            "Question-type counts must equal the requested question count"
        )

    difficulties = list(difficulty_counts)
    question_types = list(question_type_counts)

    # Group available questions by difficulty and question type.
    groups = {}

    for question_id in selected:
        details = question_details.get(question_id)

        if not details:
            continue

        difficulty = details.get("difficulty")
        question_type = details.get("question_type")

        if difficulty not in difficulty_counts:
            continue

        if question_type not in question_type_counts:
            continue

        groups.setdefault(
            (difficulty, question_type), []
        ).append(question_id)

    # Randomize available questions within each group.
    for group in groups.values():
        if randomize:
            rng.shuffle(group)

    # Build a maximum-flow network to satisfy both distributions.
    source = "source"
    sink = "sink"

    graph = {}

    def add_edge(start, end, capacity):
        graph.setdefault(start, {})
        graph.setdefault(end, {})

        graph[start][end] = capacity
        graph[end][start] = 0

    for difficulty in difficulties:
        add_edge(
            source,
            ("difficulty", difficulty),
            difficulty_counts[difficulty]
        )

    for question_type in question_types:
        add_edge(
            ("type", question_type),
            sink,
            question_type_counts[question_type]
        )

    for difficulty in difficulties:
        for question_type in question_types:
            available = len(
                groups.get((difficulty, question_type), [])
            )

            add_edge(
                ("difficulty", difficulty),
                ("type", question_type),
                available
            )

    # Find maximum flow using breadth-first search.
    total_flow = 0

    while True:
        parent = {source: None}
        queue = [source]

        while queue and sink not in parent:
            current = queue.pop(0)

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

        if sink not in parent:
            break

        flow = float("inf")
        current = sink

        while current != source:
            previous = parent[current]
            flow = min(
                flow,
                graph[previous][current]
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

    # Select questions according to the calculated flow.
    paper = []

    for difficulty in difficulties:
        difficulty_node = ("difficulty", difficulty)

        for question_type in question_types:
            type_node = ("type", question_type)

            selected_count = graph[type_node][difficulty_node]

            if selected_count:
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
    
