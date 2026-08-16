from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.core.security import create_access_token, generate_reset_token, hash_password, hash_reset_token, verify_password
from app.models.system import AuditLog, PasswordResetToken
from app.models.user import Profile, User

logger = get_logger(__name__)

RESET_TOKEN_TTL_MINUTES = 30


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


async def request_password_reset(db: AsyncSession, *, email: str) -> None:
    """Always safe to call regardless of whether the account exists — the
    caller (the API route) must return the same response either way, or this
    endpoint becomes a user-enumeration oracle. The raw token is never
    returned to the HTTP caller (that would let anyone reset anyone's
    password just by knowing their email — see PasswordResetToken's
    docstring for why only its hash is stored).

    No email-sending integration exists in this codebase yet (see CLAUDE.md).
    Until one is added, the generated token is logged server-side only, as an
    explicit interim measure so a support-assisted reset is still possible —
    production logs must be treated as sensitive as long as this is true."""
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        return

    raw_token, token_hash = generate_reset_token()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=RESET_TOKEN_TTL_MINUTES)
    db.add(PasswordResetToken(user_id=user.id, token_hash=token_hash, expires_at=expires_at))
    db.add(AuditLog(actor_user_id=user.id, action="auth.password_reset_requested"))
    logger.info(
        "password_reset_token_generated",
        user_id=str(user.id), raw_token=raw_token, expires_at=expires_at.isoformat(),
        note="No email transport configured — deliver this token to the user manually until one is added.",
    )


async def reset_password(db: AsyncSession, *, raw_token: str, new_password: str) -> bool:
    token_hash = hash_reset_token(raw_token)
    result = await db.execute(select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash))
    reset_token = result.scalar_one_or_none()
    now = datetime.now(timezone.utc)
    if reset_token is None or reset_token.used_at is not None or reset_token.expires_at < now:
        return False

    user = await db.get(User, reset_token.user_id)
    if user is None or not user.is_active:
        return False

    user.hashed_password = hash_password(new_password)
    reset_token.used_at = now
    db.add(AuditLog(actor_user_id=user.id, action="auth.password_reset_completed"))
    return True
