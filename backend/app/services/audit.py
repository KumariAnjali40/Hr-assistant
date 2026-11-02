from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog


def audit(session: AsyncSession, user_id: str, action: str, **detail) -> None:
    session.add(AuditLog(user_id=user_id, action=action, detail=detail))
