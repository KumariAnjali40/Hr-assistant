from app.auth import effective_roles
from app.rag.retriever import build_filter


def test_hierarchy():
    assert effective_roles({"hr"}) == {"hr", "manager", "employee"}
    assert effective_roles({"manager"}) == {"manager", "employee"}
    assert effective_roles({"employee"}) == {"employee"}


def test_unknown_roles_dropped():
    assert effective_roles({"offline_access", "uma_authorization"}) == frozenset()


def test_filter_uses_only_effective_roles():
    f = build_filter(effective_roles({"employee"}))
    assert f.must[0].match.any == ["employee"]  # employee can never match manager-only chunks
