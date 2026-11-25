from datetime import datetime, timedelta

from app.auth import create_access_token
from app.models import AdminActivityLog, Exam, QuestionBank, User
from app.question_bank_models import QuestionCollection, QuestionCollectionItem


def create_user(db, role, email):
    user = User(
        full_name=f"Question Bank {role.title()}",
        email=email,
        password_hash="test-password-hash",
        role=role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def auth_headers(user):
    token = create_access_token({"sub": str(user.id)})
    return {"Authorization": f"Bearer {token}"}


def add_bank_with_questions(db, owner, name, subject, question_specs):
    bank = QuestionCollection(
        name=name,
        subject=subject,
        description="Test bank",
        created_by=owner.id,
    )
    db.add(bank)
    db.flush()

    for text, question_type, difficulty, marks in question_specs:
        question = QuestionBank(
            question_text=text,
            question_type=question_type,
            subject=subject,
            difficulty=difficulty,
            marks=marks,
            negative_marks=0,
            created_by=owner.id,
        )
        db.add(question)
        db.flush()
        db.add(QuestionCollectionItem(collection_id=bank.id, question_id=question.id))

    db.commit()
    db.refresh(bank)
    return bank


def test_browse_returns_all_creators_and_complete_question_bank_summary(client, db_session):
    admin = create_user(db_session, "admin", "bank_summary_admin@test.com")
    examiner = create_user(db_session, "examiner", "bank_summary_examiner@test.com")
    admin_bank = add_bank_with_questions(
        db_session,
        admin,
        "Admin Mathematics",
        "Mathematics",
        [
            ("Addition", "MCQ", "easy", 2),
            ("Algebra", "long_answer", "hard", 5),
        ],
    )
    examiner_bank = add_bank_with_questions(
        db_session,
        examiner,
        "Examiner Science",
        "Science",
        [("Physics", "short_answer", "medium", 3)],
    )

    response = client.get("/question-banks/browse", headers=auth_headers(examiner))

    assert response.status_code == 200
    banks = response.json()
    assert {bank["id"] for bank in banks} == {admin_bank.id, examiner_bank.id}

    admin_summary = next(bank for bank in banks if bank["id"] == admin_bank.id)
    assert admin_summary["created_by_name"] == admin.full_name
    assert admin_summary["created_by_role"] == "admin"
    assert admin_summary["subject"] == "Mathematics"
    assert admin_summary["question_count"] == 2
    assert admin_summary["maximum_marks"] == 7
    assert admin_summary["question_types"] == {"MCQ": 1, "long_answer": 1}
    assert admin_summary["difficulty_counts"] == {"easy": 1, "hard": 1}
    assert admin_summary["created_at"] is not None


def test_manage_question_banks_returns_only_signed_in_users_banks(client, db_session):
    admin = create_user(db_session, "admin", "bank_owner_admin@test.com")
    examiner = create_user(db_session, "examiner", "bank_owner_examiner@test.com")
    admin_bank = add_bank_with_questions(db_session, admin, "Admin Bank", "Math", [])
    add_bank_with_questions(db_session, examiner, "Examiner Bank", "Science", [])

    response = client.get("/question-banks/", headers=auth_headers(admin))

    assert response.status_code == 200
    assert [bank["id"] for bank in response.json()] == [admin_bank.id]


def test_creator_cannot_edit_another_users_question_bank(client, db_session):
    owner = create_user(db_session, "examiner", "bank_edit_owner@test.com")
    other_examiner = create_user(db_session, "examiner", "bank_edit_other@test.com")
    bank = add_bank_with_questions(db_session, owner, "Owned Bank", "Math", [])

    response = client.patch(
        f"/question-banks/{bank.id}",
        json={"name": "Changed by another user", "subject": "Math", "description": None},
        headers=auth_headers(other_examiner),
    )

    assert response.status_code == 404
    db_session.refresh(bank)
    assert bank.name == "Owned Bank"



def test_question_bank_questions_cannot_be_copied_after_exam_start(client, db_session):
    creator = create_user(db_session, "examiner", "bank_copy_after_start@test.com")
    exam = Exam(
        title="Started Destination Exam",
        subject="Science",
        duration_minutes=30,
        total_questions=1,
        start_time=datetime.utcnow() - timedelta(minutes=1),
        created_by=creator.id,
    )
    bank = QuestionCollection(
        name="Source Questions",
        subject="Science",
        created_by=creator.id,
    )
    db_session.add_all([exam, bank])
    db_session.flush()
    question = QuestionBank(
        question_text="Source question",
        question_type="MCQ",
        subject="Science",
        difficulty="easy",
        marks=1,
        created_by=creator.id,
    )
    db_session.add(question)
    db_session.flush()
    db_session.add(QuestionCollectionItem(
        collection_id=bank.id,
        question_id=question.id,
    ))
    db_session.commit()

    response = client.post(
        f"/question-banks/select-for-exam/{exam.id}",
        json={"question_ids": [question.id]},
        headers=auth_headers(creator),
    )

    assert response.status_code == 409
    assert response.json()["detail"] == (
        "The examination has started. Its question bank can no longer be changed."
    )

def test_question_bank_creation_log_contains_saved_bank_id(client, db_session):
    admin = create_user(db_session, "admin", "bank_creation_log_admin@test.com")

    response = client.post(
        "/question-banks/",
        json={"name": "Logged Bank", "subject": "Mathematics", "description": "Audit test"},
        headers=auth_headers(admin),
    )

    assert response.status_code == 201
    bank_id = response.json()["bank_id"]
    log = db_session.query(AdminActivityLog).filter(
        AdminActivityLog.actor_user_id == admin.id,
        AdminActivityLog.action == "question_bank_created",
    ).one()
    assert log.details["bank_id"] == bank_id
    assert log.details["bank_name"] == "Logged Bank"

