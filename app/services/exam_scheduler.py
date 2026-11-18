
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import and_

from app.database import SessionLocal
from app.models import ExamSession


scheduler = BackgroundScheduler(
    timezone="UTC"
)


def submit_expired_exam_sessions():
    """
    Automatically submits all exam sessions
    whose server-side deadline has expired.
    """

    if SessionLocal is None:
        return

    db = SessionLocal()

    try:
        now = datetime.utcnow()

        expired_sessions = db.query(
            ExamSession
        ).filter(
            and_(
                ExamSession.status == "in_progress",
                ExamSession.expires_at <= now
            )
        ).all()

        if not expired_sessions:
            return

        for session in expired_sessions:
            session.status = "submitted"
            session.submitted_at = now

        db.commit()

        print(
            f"Automatically submitted "
            f"{len(expired_sessions)} expired exam session(s)."
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
          
