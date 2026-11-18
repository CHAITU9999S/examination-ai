from getpass import getpass

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import hash_password
from app.database import SessionLocal
from app.models import User


def create_initial_admin(
    db: Session,
    full_name: str,
    email: str,
    password: str,
) -> User:
    """
    Create the first Admin only when no Admin account exists.

    PostgreSQL advisory locking prevents two bootstrap processes from
    creating the first Admin at the same time.
    """

    full_name = full_name.strip()
    email = email.strip().lower()

    if len(full_name) < 2 or len(full_name) > 150:
        raise ValueError("Full name must contain 2 to 150 characters.")

    if "@" not in email or len(email) > 255:
        raise ValueError("Enter a valid email address.")

    if len(password) < 8 or len(password) > 128:
        raise ValueError("Password must contain 8 to 128 characters.")

    try:
        with db.begin():
            if db.bind.dialect.name == "postgresql":
                db.execute(
                    text("SELECT pg_advisory_xact_lock(:lock_id)"),
                    {"lock_id": 6842197301},
                )

            existing_admin = db.query(User).filter(
                User.role == "admin"
            ).first()

            if existing_admin is not None:
                raise RuntimeError(
                    "An Admin account already exists. "
                    "Initial Admin creation is disabled."
                )

            admin = User(
                full_name=full_name,
                email=email,
                password_hash=hash_password(password),
                role="admin",
                is_active=True,
            )

            db.add(admin)
            db.flush()
            db.refresh(admin)

        return admin

    except IntegrityError as exc:
        raise RuntimeError(
            "Could not create the initial Admin. "
            "Check whether this email is already registered."
        ) from exc


def main() -> None:
    print("\nExamGuard AI - Initial Admin Setup")
    print("----------------------------------")
    print("This setup works only when the database has no Admin account.")
    print("Do not share or commit the password.\n")

    full_name = input("Admin full name: ").strip()
    email = input("Admin email: ").strip()
    password = getpass("Admin password (minimum 8 characters): ")
    confirm_password = getpass("Confirm admin password: ")

    if password != confirm_password:
        raise SystemExit("The passwords do not match.")

    db = SessionLocal()

    try:
        admin = create_initial_admin(
            db=db,
            full_name=full_name,
            email=email,
            password=password,
        )
        print("\nInitial Admin created successfully.")
        print(f"Admin account ID: {admin.id}")
        print(f"Admin email: {admin.email}")
        print("You can now log in through POST /auth/login.")

    except (ValueError, RuntimeError) as exc:
        raise SystemExit(f"Setup stopped: {exc}") from exc

    finally:
        db.close()


if __name__ == "__main__":
    main()
