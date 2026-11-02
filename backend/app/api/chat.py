import asyncio
import json
import time
import uuid

import structlog
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.graph import get_agent
from app.auth import User
from app.config import settings
from app.db import SessionLocal, get_session
from app.models import Conversation, Message
from app.services.audit import audit
from app.services.guardrails import GuardrailError, check_input, redact
from app.services.ratelimit import rate_limit

router = APIRouter(prefix="/api", tags=["chat"])
log = structlog.get_logger()


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    conversation_id: uuid.UUID | None = None


def sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@router.post("/chat")
async def chat(req: ChatRequest, user: User = Depends(rate_limit), session: AsyncSession = Depends(get_session)):
    try:
        text = check_input(req.message)
    except GuardrailError as e:
        raise HTTPException(400, str(e))

    if req.conversation_id:
        conv = await session.get(Conversation, req.conversation_id)
        if not conv or conv.user_id != user.id:  # ownership check: never leak other users' chats
            raise HTTPException(404, "Conversation not found")
    else:
        conv = Conversation(user_id=user.id, title=text[:60])
        session.add(conv)
        await session.flush()

    rows = (
        await session.scalars(
            select(Message)
            .where(Message.conversation_id == conv.id)
            .order_by(Message.created_at.desc())
            .limit(settings.history_turns * 2)
        )
    ).all()
    history = [(m.role, m.content) for m in reversed(rows)]
    session.add(Message(conversation_id=conv.id, role="user", content=text))
    await session.commit()
    conv_id = conv.id

    async def event_stream():
        started = time.perf_counter()
        parts: list[str] = []
        tools_used: list[str] = []
        sources: list[dict] = []
        ok = True
        yield sse("meta", {"conversation_id": str(conv_id)})
        ctx = {"user_id": user.username, "roles": user.roles, "sources": sources}
        try:
            async with asyncio.timeout(settings.request_timeout_s):
                async for ev in get_agent().astream_events(
                    {"messages": history + [("user", text)]},
                    config={"configurable": ctx, "recursion_limit": 10},
                    version="v2",
                ):
                    kind = ev["event"]
                    if kind == "on_chat_model_stream":
                        c = ev["data"]["chunk"].content
                        if isinstance(c, str) and c:
                            parts.append(c)
                            yield sse("token", {"text": c})
                    elif kind == "on_tool_start":
                        tools_used.append(ev["name"])
                        yield sse("tool", {"name": ev["name"]})
        except Exception:
            ok = False
            log.exception("chat_failed", conversation_id=str(conv_id))
            yield sse("error", {"message": "Something went wrong. Please try again, or raise an HR ticket."})

        if ok:
            uniq = list({(s["policy"], s["version"], s["page"]): s for s in sources}.values())
            async with SessionLocal() as s:  # own session: request-scoped one may be closed by now
                msg = Message(conversation_id=conv_id, role="assistant", content="".join(parts), sources=uniq)
                s.add(msg)
                audit(
                    s, user.id, "chat",
                    question=redact(text)[:500], tools=tools_used, sources=uniq,
                    latency_ms=round((time.perf_counter() - started) * 1000),
                )
                await s.commit()
            yield sse("sources", {"sources": uniq})
            yield sse("done", {"message_id": str(msg.id)})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
