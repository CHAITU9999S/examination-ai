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
