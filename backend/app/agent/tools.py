"""Agent tools.

SECURITY: identity (user_id) and roles come from `config["configurable"]`, which the
backend fills from the verified JWT. They are NOT tool parameters, so the LLM can never
be talked into querying someone else's data.
"""
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

from app.rag.retriever import retrieve
from app.services.hrms import get_hrms


@tool
async def search_policy(query: str, config: RunnableConfig) -> str:
    """Search company HR policy documents (leave, holidays, payroll rules, benefits,
    reimbursements, conduct). Use for any general policy question."""
    ctx = config["configurable"]
    chunks = await retrieve(query, ctx["roles"])
    if not chunks:
        return "NO_RELEVANT_POLICY_FOUND"
    for c in chunks:
        ctx["sources"].append({"policy": c.policy_name, "version": c.version, "page": c.page})
    return "\n\n".join(
        f'<policy name="{c.policy_name}" version="{c.version}" page="{c.page}">\n{c.text}\n</policy>' for c in chunks
    )


@tool
async def get_my_leave_balance(config: RunnableConfig) -> str:
    """Get the CURRENT USER's own leave balance (casual, sick, earned). Takes no arguments."""
    return str(await get_hrms().leave_balance(config["configurable"]["user_id"]))


@tool
async def get_my_next_payday(config: RunnableConfig) -> str:
    """Get the CURRENT USER's salary credit schedule and payslip availability. Takes no arguments."""
    return str(await get_hrms().next_payday(config["configurable"]["user_id"]))


@tool
async def create_hr_ticket(summary: str, config: RunnableConfig) -> str:
    """Raise an HR ticket on behalf of the current user when the question cannot be answered
    from policies or needs a human. `summary` is a short description of the issue."""
    return str(await get_hrms().create_ticket(config["configurable"]["user_id"], summary[:500]))


TOOLS = [search_policy, get_my_leave_balance, get_my_next_payday, create_hr_ticket]
