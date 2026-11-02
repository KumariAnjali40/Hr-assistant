"""HRMS / payroll integration boundary.

Tools call this interface with the *authenticated* user's id. Swap MockHRMS for
HttpHRMS (or a SAP / Workday / Keka client) without touching the agent.
"""
import uuid
from typing import Protocol

import httpx

from app.config import settings


class HRMS(Protocol):
    async def leave_balance(self, employee_id: str) -> dict: ...
    async def next_payday(self, employee_id: str) -> dict: ...
    async def create_ticket(self, employee_id: str, summary: str) -> dict: ...


class MockHRMS:
    _LEAVES = {
        "alice": {"casual": 7, "sick": 9, "earned": 14.5},
        "bob": {"casual": 4, "sick": 10, "earned": 22},
        "hradmin": {"casual": 12, "sick": 10, "earned": 3},
    }

    async def leave_balance(self, employee_id: str) -> dict:
        return {"employee_id": employee_id, "balance_days": self._LEAVES.get(employee_id, {"casual": 12, "sick": 10, "earned": 0})}

    async def next_payday(self, employee_id: str) -> dict:
        return {"rule": "Last working day of the month", "payslip_available": "by the 3rd of next month"}

    async def create_ticket(self, employee_id: str, summary: str) -> dict:
        return {"ticket_id": f"HR-{uuid.uuid4().hex[:6].upper()}", "status": "open"}


class HttpHRMS:
    def __init__(self, base_url: str):
        self._c = httpx.AsyncClient(base_url=base_url, timeout=10)

    async def _get(self, path: str) -> dict:
        r = await self._c.get(path)
        r.raise_for_status()
        return r.json()

    async def leave_balance(self, employee_id: str) -> dict:
        return await self._get(f"/employees/{employee_id}/leave-balance")

    async def next_payday(self, employee_id: str) -> dict:
        return await self._get(f"/employees/{employee_id}/payroll/schedule")

    async def create_ticket(self, employee_id: str, summary: str) -> dict:
        r = await self._c.post("/tickets", json={"employee_id": employee_id, "summary": summary})
        r.raise_for_status()
        return r.json()


_hrms: HRMS | None = None


def get_hrms() -> HRMS:
    global _hrms
    if _hrms is None:
        _hrms = HttpHRMS(settings.hrms_base_url) if settings.hrms_base_url else MockHRMS()
    return _hrms
