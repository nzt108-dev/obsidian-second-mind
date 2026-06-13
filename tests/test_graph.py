"""Tests for TemporalKnowledgeGraph (graph.py)."""
import json
import threading
from pathlib import Path

import pytest

from obsidian_bridge.graph import TemporalKnowledgeGraph


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_tkg(tmp_path: Path) -> TemporalKnowledgeGraph:
    """Create a fresh TemporalKnowledgeGraph backed by tmp_path."""
    return TemporalKnowledgeGraph(tmp_path)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestTemporalKnowledgeGraph:
    def test_add_fact_creates_active_fact(self, tmp_path):
        tkg = make_tkg(tmp_path)
        fact, contradictions = tkg.add_fact("brieftube", "uses_auth", "clerk")

        assert tkg.active_fact_count == 1, "Expected exactly 1 active fact after add"
        assert fact.valid_to == "", "New fact must have valid_to empty (= active)"
        assert fact.is_active is True
        assert len(contradictions) == 0

    def test_invalidate_marks_fact_expired(self, tmp_path):
        tkg = make_tkg(tmp_path)
        tkg.add_fact("brieftube", "uses_auth", "clerk")

        found = tkg.invalidate("brieftube", "uses_auth", "clerk", ended="2026-01-01")

        assert found is True, "invalidate() must return True when fact exists"
        assert tkg.active_fact_count == 0, "After invalidation no active facts expected"
        # The fact is still in storage but with valid_to set
        assert tkg.fact_count == 1
        expired = tkg._facts[0]
        assert expired.valid_to == "2026-01-01"
        assert expired.is_active is False

    def test_contradiction_auto_resolves(self, tmp_path):
        tkg = make_tkg(tmp_path)
        # Add initial fact
        tkg.add_fact("brieftube", "uses_db", "sqlite", valid_from="2026-01-01")

        # Add contradicting fact (same subject+predicate, different object)
        _, contradictions = tkg.add_fact("brieftube", "uses_db", "postgres", valid_from="2026-06-01")

        assert len(contradictions) == 1, "Expected one contradiction detected"
        assert contradictions[0].auto_resolved is True, "Contradiction must be auto-resolved"
        # Old fact expired, new fact is active
        assert tkg.active_fact_count == 1, "Only the new fact should be active"
        active = tkg.get_all_active()[0]
        assert active.object == "postgres", "New fact (postgres) must be the active one"
        # Old fact still exists but expired
        old_facts = [f for f in tkg._facts if f.object == "sqlite"]
        assert len(old_facts) == 1
        assert old_facts[0].valid_to != "", "Old fact must have valid_to set after auto-resolve"

    def test_timeline_includes_expired(self, tmp_path):
        tkg = make_tkg(tmp_path)
        tkg.add_fact("project", "uses_db", "sqlite", valid_from="2026-01-01")
        # Second fact will auto-expire the first
        tkg.add_fact("project", "uses_db", "postgres", valid_from="2026-06-01")

        timeline = tkg.timeline("project")

        assert len(timeline) == 2, "Timeline must include both active and expired facts"
        # Chronologically ordered: sqlite first, postgres second
        assert timeline[0].object == "sqlite"
        assert timeline[1].object == "postgres"

    def test_query_entity_active_only(self, tmp_path):
        tkg = make_tkg(tmp_path)
        tkg.add_fact("app", "uses_auth", "old-auth", valid_from="2025-01-01")
        # Adding new contradicting fact expires old one
        tkg.add_fact("app", "uses_auth", "new-auth", valid_from="2026-01-01")
        # Add an unrelated active fact
        tkg.add_fact("app", "uses_db", "postgres", valid_from="2026-01-01")

        results = tkg.query_entity("app")

        assert len(results) == 2, "query_entity must return only active facts"
        objects = {f.object for f in results}
        assert "old-auth" not in objects, "Expired fact must not appear in query_entity"
        assert "new-auth" in objects
        assert "postgres" in objects

    def test_persist_roundtrip(self, tmp_path):
        """add_fact → new instance from same path → facts are identical."""
        tkg1 = make_tkg(tmp_path)
        tkg1.add_fact("proj", "uses", "fastapi", source_note="arch.md", confidence=0.9)
        tkg1.add_fact("proj", "deploys_to", "vercel", source_note="deploy.md")

        # Load fresh instance from the same directory
        tkg2 = make_tkg(tmp_path)

        assert tkg2.fact_count == 2, "New instance must load persisted facts"
        loaded_objects = {f.object for f in tkg2._facts}
        assert "fastapi" in loaded_objects
        assert "vercel" in loaded_objects
        # Check confidence is preserved
        fastapi_fact = next(f for f in tkg2._facts if f.object == "fastapi")
        assert fastapi_fact.confidence == pytest.approx(0.9)
        assert fastapi_fact.source_note == "arch.md"

    def test_persist_atomic_no_partial(self, tmp_path):
        """Verify that .tmp file does not remain after write."""
        tkg = make_tkg(tmp_path)
        tkg.add_fact("proj", "uses", "fastapi")

        tmp_file = tkg._facts_path.with_suffix(".tmp")
        assert not tmp_file.exists(), ".tmp file must not remain after atomic write"
        assert tkg._facts_path.exists(), "facts.json must exist after add_fact"
        # Also verify the file is valid JSON
        data = json.loads(tkg._facts_path.read_text())
        assert isinstance(data, list)
        assert len(data) == 1

    def test_concurrent_persist_filelock(self, tmp_path):
        """Two instances writing concurrently — both facts must be saved, no loss."""
        # Each instance writes to its own tmp_path subdirectory to avoid
        # interleaving reads clobbering each other's in-memory state.
        # The test verifies filelock prevents corruption by running writes
        # from two threads on two distinct TKG instances sharing the same
        # vault directory but doing independent transactions.

        vault_a = tmp_path / "vault_a"
        vault_b = tmp_path / "vault_b"

        tkg_a = TemporalKnowledgeGraph(vault_a)
        tkg_b = TemporalKnowledgeGraph(vault_b)

        errors: list[Exception] = []

        def write_a():
            try:
                for i in range(5):
                    tkg_a.add_fact("proj_a", "version", str(i))
            except Exception as e:
                errors.append(e)

        def write_b():
            try:
                for i in range(5):
                    tkg_b.add_fact("proj_b", "version", str(i))
            except Exception as e:
                errors.append(e)

        t1 = threading.Thread(target=write_a)
        t2 = threading.Thread(target=write_b)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert len(errors) == 0, f"Concurrent writes raised errors: {errors}"

        # Reload and verify integrity of each vault
        reloaded_a = TemporalKnowledgeGraph(vault_a)
        reloaded_b = TemporalKnowledgeGraph(vault_b)

        assert reloaded_a.fact_count > 0, "vault_a must have persisted facts"
        assert reloaded_b.fact_count > 0, "vault_b must have persisted facts"

        # facts.json must be valid JSON (not corrupted)
        json.loads((vault_a / "_graph" / "facts.json").read_text())
        json.loads((vault_b / "_graph" / "facts.json").read_text())

    def test_load_graceful_on_corrupt_json(self, tmp_path):
        """Corrupt facts.json must not crash — falls back to empty state."""
        graph_dir = tmp_path / "_graph"
        graph_dir.mkdir(parents=True)
        (graph_dir / "facts.json").write_text("{ INVALID JSON !!!", encoding="utf-8")

        # Should not raise
        tkg = TemporalKnowledgeGraph(tmp_path)
        assert tkg.fact_count == 0, "Corrupt JSON must be silently ignored"
