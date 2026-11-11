
import pytest

from app.services.paper_generator import generate_paper


def test_same_student_gets_same_paper():
    questions = [1, 2, 3, 4, 5, 6]

    first = generate_paper(questions, 101, 1, 4)
    second = generate_paper(questions, 101, 1, 4)

    assert first == second


def test_different_students_get_different_papers():
    questions = list(range(1, 101))

    first = generate_paper(questions, 101, 1, 50)
    second = generate_paper(questions, 102, 1, 50)

    assert first != second


def test_rejects_more_questions_than_available():
    with pytest.raises(ValueError):
        generate_paper([1, 2], 101, 1, 5)


def test_rejects_zero_questions():
    with pytest.raises(ValueError):
        generate_paper([1, 2], 101, 1, 0)


def test_rejects_negative_questions():
    with pytest.raises(ValueError):
        generate_paper([1, 2], 101, 1, -1)


def test_generated_paper_has_requested_count():
    questions = list(range(1, 21))

    paper = generate_paper(questions, 101, 1, 10)

    assert len(paper) == 10


def test_generated_paper_has_no_duplicates():
    questions = list(range(1, 21))

    paper = generate_paper(questions, 101, 1, 15)

    assert len(paper) == len(set(paper))


def test_distribution_based_paper_has_correct_counts():
    question_ids = [1, 2, 3, 4, 5, 6, 7, 8]

    question_details = {
        1: {"difficulty": "Easy", "question_type": "MCQ"},
        2: {"difficulty": "Easy", "question_type": "MCQ"},
        3: {"difficulty": "Easy", "question_type": "short_answer"},
        4: {"difficulty": "Medium", "question_type": "MCQ"},
        5: {"difficulty": "Medium", "question_type": "short_answer"},
        6: {"difficulty": "Hard", "question_type": "MCQ"},
        7: {"difficulty": "Hard", "question_type": "long_answer"},
        8: {"difficulty": "Hard", "question_type": "long_answer"}
    }

    paper = generate_paper(
        question_ids,
        101,
        1,
        4,
        question_details=question_details,
        difficulty_counts={
            "Easy": 2,
            "Medium": 1,
            "Hard": 1
        },
        question_type_counts={
            "MCQ": 2,
            "short_answer": 1,
            "long_answer": 1
        }
    )

    assert len(paper) == 4

    assert sum(
        question_details[q]["difficulty"] == "Easy"
        for q in paper
    ) == 2

    assert sum(
        question_details[q]["difficulty"] == "Medium"
        for q in paper
    ) == 1

    assert sum(
        question_details[q]["difficulty"] == "Hard"
        for q in paper
    ) == 1

    assert sum(
        question_details[q]["question_type"] == "MCQ"
        for q in paper
    ) == 2

    assert sum(
        question_details[q]["question_type"] == "short_answer"
        for q in paper
    ) == 1

    assert sum(
        question_details[q]["question_type"] == "long_answer"
        for q in paper
    ) == 1


def test_distribution_based_paper_is_deterministic():
    question_ids = [1, 2, 3, 4, 5, 6]

    question_details = {
        1: {"difficulty": "Easy", "question_type": "MCQ"},
        2: {"difficulty": "Easy", "question_type": "MCQ"},
        3: {"difficulty": "Medium", "question_type": "short_answer"},
        4: {"difficulty": "Medium", "question_type": "short_answer"},
        5: {"difficulty": "Hard", "question_type": "long_answer"},
        6: {"difficulty": "Hard", "question_type": "long_answer"}
    }

    rules = {
        "question_details": question_details,
        "difficulty_counts": {
            "Easy": 1,
            "Medium": 1,
            "Hard": 1
        },
        "question_type_counts": {
            "MCQ": 1,
            "short_answer": 1,
            "long_answer": 1
        }
    }

    first = generate_paper(
        question_ids,
        101,
        1,
        3,
        **rules
    )

    second = generate_paper(
        question_ids,
        101,
        1,
        3,
        **rules
    )

    assert first == second


def test_rejects_incomplete_distribution_rules():
    with pytest.raises(ValueError):
        generate_paper(
            [1, 2, 3],
            101,
            1,
            2,
            difficulty_counts={"Easy": 2}
        )


def test_rejects_impossible_distribution():
    question_ids = [1, 2, 3, 4]

    question_details = {
        1: {"difficulty": "Easy", "question_type": "MCQ"},
        2: {"difficulty": "Easy", "question_type": "MCQ"},
        3: {"difficulty": "Medium", "question_type": "MCQ"},
        4: {"difficulty": "Medium", "question_type": "MCQ"}
    }

    with pytest.raises(ValueError):
        generate_paper(
            question_ids,
            101,
            1,
            4,
            question_details=question_details,
            difficulty_counts={
                "Easy": 2,
                "Medium": 2
            },
            question_type_counts={
                "MCQ": 2,
                "short_answer": 2
            }
        )


def test_randomization_can_be_disabled():
    questions = [1, 2, 3, 4, 5, 6]

    first = generate_paper(
        questions, 101, 1, 4, randomize=False
    )

    second = generate_paper(
        questions, 102, 1, 4, randomize=False
    )

    assert first == [1, 2, 3, 4]
    assert second == [1, 2, 3, 4]
                        
