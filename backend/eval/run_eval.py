"""Retrieval evaluation + access-control leak test.

Metrics: hit@k, MRR for questions with an expected policy; leak count for `forbid` cases
(must be 0, otherwise your ACL filter is broken). Run after every change to chunking,
embedding model, k, or thresholds. Extend golden.jsonl with real HR questions (aim for 100+).
"""
import asyncio
import json
from pathlib import Path

from app.config import settings
from app.rag.retriever import retrieve
from app.auth import effective_roles


async def main():
    items = [json.loads(l) for l in (Path(__file__).parent / "golden.jsonl").read_text().splitlines() if l.strip()]
    hits, rr, n_expect, leaks = 0, 0.0, 0, 0
    for it in items:
        roles = effective_roles(set(it["roles"]))
        chunks = await retrieve(it["q"], roles, k=settings.retrieval_k, min_score=0.0, use_cache=False)
        names = [c.policy_name for c in chunks]
        if "expect" in it:
            n_expect += 1
            if it["expect"] in names:
                hits += 1
                rr += 1 / (names.index(it["expect"]) + 1)
            else:
                print(f"MISS  {it['q']!r} -> {names}")
        if "forbid" in it and it["forbid"] in names:
            leaks += 1
            print(f"LEAK  {it['q']!r} roles={it['roles']} retrieved {it['forbid']}")
    print(f"\nhit@{settings.retrieval_k}: {hits}/{n_expect} = {hits / max(n_expect, 1):.2f}")
    print(f"MRR: {rr / max(n_expect, 1):.2f}")
    print(f"ACL leaks: {leaks}")


if __name__ == "__main__":
    asyncio.run(main())
