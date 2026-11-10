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
        
