"""Index the sample policies (local dev). Re-running is safe (deterministic ids = upsert)."""
import uuid
from pathlib import Path

from app.rag.ingest import ingest

BASE = Path(__file__).resolve().parent.parent / "sample_policies"
ALL = ["employee", "manager", "hr"]
POLICIES = [
    ("leave_policy.txt", "Leave Policy", "3.0", ALL),
    ("payroll_policy.txt", "Payroll Policy", "2.1", ALL),
    ("compensation_review.txt", "Compensation Review Guidelines", "1.0", ["manager", "hr"]),  # RBAC demo
]

if __name__ == "__main__":
    for fname, name, version, roles in POLICIES:
        doc_id = str(uuid.uuid5(uuid.NAMESPACE_URL, name))
        n = ingest(doc_id, str(BASE / fname), name, version, roles)
        print(f"indexed {name} v{version}: {n} chunks, roles={roles}")
