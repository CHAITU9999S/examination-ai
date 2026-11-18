
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler

from app.database import SessionLocal
from app.models import ExamSession
from app.services.evaluation_service import evaluate_exam_session


scheduler = BackgroundScheduler(
    timezone="UTC"
)


def submit_expired_exam_sessions():
    """
    Automatically submits all exam sessions
    whose server-side deadline has expired.

    Database row locking helps prevent conflicts
    with manual submission and answer-saving requests.
    """

    if SessionLocal is None:
        return

    db = SessionLocal()

    try:
        now = datetime.utcnow()

        expired_sessions = db.query(
            ExamSession
        ).filter(
            ExamSession.status == "in_progress",
            ExamSession.expires_at <= now
        ).with_for_update(
            skip_locked=True
        ).all()

        if not expired_sessions:
            return

        expired_session_ids = [
            session.id
            for session in expired_sessions
        ]

        submitted_count = 0

        for session in expired_sessions:

            # Recheck after acquiring the row lock.
            if (
                session.status == "in_progress"
                and session.expires_at <= now
            ):
                session.status = "submitted"
                session.submitted_at = now
                submitted_count += 1

        if submitted_count:
            db.commit()

            print(
                f"Automatically submitted "
                f"{submitted_count} expired exam session(s)."
            )

            # Objective answers are evaluated immediately after the
            # server-side timer submits each session. Subjective answers
            # remain pending for examiner review.
            for session_id in expired_session_ids:
                try:
                    evaluate_exam_session(
                        db,
                        session_id,
                    )
                except Exception as error:
                    db.rollback()
                    print(
                        f"Automatic evaluation failed for session "
                        f"{session_id}:",
                        str(error),
                    )

    except Exception as error:
        db.rollback()

        print(
            "Exam scheduler error:",
            str(error)
        )

    finally:
        db.close()


def start_exam_scheduler():
    """
    Starts the background scheduler.
    """

    if scheduler.running:
        return

    scheduler.add_job(
        submit_expired_exam_sessions,
        trigger="interval",
        seconds=10,
        id="automatic_exam_submission",
        replace_existing=True,
        max_instances=1,
        coalesce=True
    )

    scheduler.start()

    print("Exam submission scheduler started.")


def stop_exam_scheduler():
    """
    Stops the background scheduler.
    """

    if scheduler.running:
        scheduler.shutdown(wait=False)

        print("Exam submission scheduler stopped.")
                
