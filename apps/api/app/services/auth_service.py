from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, hash_password, verify_password
from app.models.system import AuditLog
from app.models.user import Profile, User


class AuthError(Exception):
    pass


async def register_user(db: AsyncSession, *, email: str, password: str, full_name: str | None) -> tuple[User, str]:
    existing = await db.execute(select(User).where(User.email == email))
    if existing.scalar_one_or_none() is not None:
        raise AuthError("An account with this email already exists.")

    user = User(email=email, hashed_password=hash_password(password), full_name=full_name)
    db.add(user)
    await db.flush()
    db.add(Profile(user_id=user.id, display_name=full_name))
    db.add(AuditLog(actor_user_id=user.id, action="user.register"))
    await db.flush()

    token = create_access_token(user.id)
    return user, token


async def authenticate_user(db: AsyncSession, *, email: str, password: str) -> tuple[User, str]:
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(password, user.hashed_password):
        raise AuthError("Invalid email or password.")
    if not user.is_active:
        raise AuthError("This account has been deactivated.")

    db.add(AuditLog(actor_user_id=user.id, action="user.login"))
    token = create_access_token(user.id)
    return user, token
