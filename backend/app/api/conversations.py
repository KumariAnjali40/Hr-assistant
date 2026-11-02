import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import User, current_user
from app.db import get_session
from app.models import Conversation, Feedback, Message

router = APIRouter(prefix="/api", tags=["conversations"])


async def _owned(session: AsyncSession, cid: uuid.UUID, user: User) -> Conversation:
    conv = await session.get(Conversation, cid)
    if not conv or conv.user_id != user.id:
        raise HTTPException(404, "Conversation not found")
    return conv


@router.get("/conversations")
async def list_conversations(user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    rows = await session.scalars(
        select(Conversation).where(Conversation.user_id == user.id).order_by(Conversation.created_at.desc()).limit(50)
    )
    return [{"id": str(c.id), "title": c.title} for c in rows]


@router.get("/conversations/{cid}/messages")
async def get_messages(cid: uuid.UUID, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    await _owned(session, cid, user)
    rows = await session.scalars(select(Message).where(Message.conversation_id == cid).order_by(Message.created_at))
    return [{"id": str(m.id), "role": m.role, "content": m.content, "sources": m.sources or []} for m in rows]


@router.delete("/conversations/{cid}", status_code=204)
async def delete_conversation(cid: uuid.UUID, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    await _owned(session, cid, user)
    await session.execute(delete(Conversation).where(Conversation.id == cid))
    await session.commit()


class FeedbackIn(BaseModel):
    rating: int = Field(ge=-1, le=1)
    comment: str | None = Field(None, max_length=1000)


@router.post("/messages/{mid}/feedback", status_code=204)
async def feedback(mid: uuid.UUID, body: FeedbackIn, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    msg = await session.get(Message, mid)
    if not msg:
        raise HTTPException(404, "Message not found")
    await _owned(session, msg.conversation_id, user)
    session.add(Feedback(message_id=mid, user_id=user.id, rating=body.rating, comment=body.comment))
    await session.commit()
