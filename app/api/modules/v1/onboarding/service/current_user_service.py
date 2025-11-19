from typing import Optional
from uuid import UUID

from sqlmodel import Session

from app.api.modules.v1.users.models.users_model import User


def get_user_by_id(db: Session, user_id: UUID) -> Optional[User]:
    """Return a `User` by its id, or `None` when not found.

    Args:
        db: SQLModel/SQLAlchemy session.
        user_id: UUID of the user to retrieve.

    Returns:
        Optional[User]: The User instance or None if not found.
    """
    # SQLModel's Session implements ``get`` which is efficient for primary-key lookups.
    try:
        return db.get(User, user_id)
    except Exception:
        # Keep this helper safe: callers may handle or log errors as they prefer.
        return None


def get_user_by_email(db: Session, email: str) -> Optional[User]:
    """Return a `User` by email, or `None` when not found.

    Args:
        db: SQLModel/SQLAlchemy session.
        email: Email address to look up.
    """
    try:
        statement = db.exec(User.select().where(User.email == email))
        return statement.first()
    except Exception:
        return None


def require_current_user(db: Session, user_id: UUID) -> User:
    """Return the current user or raise `ValueError` when not found.

    This function is a convenience for service code that expects an authenticated
    user to exist; the caller (route/dependency) should catch the `ValueError`
    and translate it into an HTTP 401/403 as appropriate for your app.
    """
    user = get_user_by_id(db, user_id)
    if not user:
        raise ValueError("Authenticated user not found")
    return user
