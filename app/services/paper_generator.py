import random


def generate_paper(question_ids, student_id, exam_id, number_of_questions):
    if number_of_questions <= 0:
        raise ValueError("Number of questions must be positive")

    if number_of_questions > len(question_ids):
        raise ValueError("Not enough questions available")

    seed = f"{exam_id}-{student_id}"
    rng = random.Random(seed)

    selected = list(question_ids)
    rng.shuffle(selected)

    return selected[:number_of_questions]
