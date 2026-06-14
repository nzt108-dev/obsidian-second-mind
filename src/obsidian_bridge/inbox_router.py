"""Inbox Auto-Router — rule-based classification of incoming captures.

Decides which project an incoming Telegram note belongs to, WITHOUT an LLM.
Used by:
    - telegram_bot.handle_message  (stream: classify each new message)
    - cli `process-inbox`          (batch: sort already-accumulated inbox/)

Rules (in priority order):
    R2  Explicit spec header ("ТЗ: <Name>", "Проект называется <Name>",
        "Project: <Name>")            → that project (new one if unknown)
    R1  A known project name is mentioned in the text → that project
    R3  No confident match                            → stays in `inbox`

The downstream wiki-spreading (cross-refs, concept stubs) is done by
ingest.IngestPipeline — this module only answers "where does it go?".
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Known project names shorter than this are ignored for R1 body-matching
# to avoid false positives on common words (e.g. a 4-char slug appearing
# incidentally in prose).
_MIN_PROJECT_NAME_LEN = 4

# Generic vault buckets that are NOT real projects — never route TO them via
# an R1 mention (the word "research" in prose must not pull a note into a
# folder literally named "research"). Notes that match only these stay in inbox.
_GENERIC_BUCKETS = {"inbox", "research", "general", "global", "global-config", "misc", "nzt108-dev", "claude-config"}

# R2 — explicit "this is a spec for project X" headers.
_NEW_PROJECT_PATTERNS = [
    re.compile(r"ТЗ\s*[:\-–—]\s*([A-Za-z][\w\- ]{1,40})", re.IGNORECASE),
    re.compile(r"проект\s+называется\s+[«\"']?([A-Za-z][\w\-]{1,40})", re.IGNORECASE),
    re.compile(r"\bProject\s*[:=]\s*([A-Za-z][\w\-]{1,40})", re.IGNORECASE),
]


@dataclass
class RouteDecision:
    """Result of classifying one capture."""

    project: str  # target project slug, or "inbox" if undecided
    note_type: str = "note"  # "note" | "research"
    reason: str = ""  # human-readable why (which rule fired)
    is_new_project: bool = False  # True if a brand-new project slug was derived


def _slugify_project(name: str) -> str:
    """Turn a captured project name into a vault-safe slug.

    Returns "" if nothing usable remains (e.g. pure non-ASCII name).
    """
    name = name.strip().strip("«»\"'").strip()
    # Keep ASCII word chars + spaces/dashes only; drop the rest.
    cleaned = re.sub(r"[^A-Za-z0-9\- ]", "", name)
    slug = re.sub(r"[\s_]+", "-", cleaned.lower()).strip("-")
    # Collapse repeated dashes.
    slug = re.sub(r"-{2,}", "-", slug)
    return slug if len(slug) >= 2 else ""


def _match_known_project(text: str, known_projects: list[str]) -> str | None:
    """R1: return the single best-matching known project, or None.

    Matches by whole-word, case-insensitive. Ignores names shorter than
    _MIN_PROJECT_NAME_LEN to avoid incidental false positives. On a tie
    between two projects, returns None (we don't guess)."""
    text_lower = text.lower()
    scores: dict[str, int] = {}
    for project in known_projects:
        if len(project) < _MIN_PROJECT_NAME_LEN:
            continue
        if project.lower() in _GENERIC_BUCKETS:
            continue
        # Word-boundary match; treat dashes as part of the token.
        pattern = re.compile(rf"(?<![\w\-]){re.escape(project.lower())}(?![\w\-])")
        count = len(pattern.findall(text_lower))
        if count:
            scores[project] = count

    if not scores:
        return None
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    if len(ranked) > 1 and ranked[0][1] == ranked[1][1]:
        return None  # tie → undecided
    return ranked[0][0]


def _detect_note_type(text: str) -> str:
    """Links → research, everything else → note."""
    if re.search(r"https?://", text):
        return "research"
    return "note"


def classify(
    text: str,
    title: str = "",
    known_projects: list[str] | None = None,
) -> RouteDecision:
    """Decide which project an incoming capture belongs to.

    Pure function — no I/O. See module docstring for the rules.
    """
    known_projects = known_projects or []
    known_lower = {p.lower() for p in known_projects}
    note_type = _detect_note_type(text)

    body = (text or "").strip()
    haystack = f"{title}\n{body}".strip()

    # Edge case: empty / too short → never route or create a project.
    if len(body) < 15:
        return RouteDecision("inbox", note_type, "too short to classify")

    # --- R2: explicit spec header naming a project ---
    for pattern in _NEW_PROJECT_PATTERNS:
        m = pattern.search(haystack)
        if not m:
            continue
        slug = _slugify_project(m.group(1))
        if not slug:
            continue
        if slug in known_lower:
            # Spec for an existing project.
            actual = next(p for p in known_projects if p.lower() == slug)
            return RouteDecision(actual, note_type, f"spec header → existing project '{actual}'")
        return RouteDecision(slug, note_type, f"spec header → new project '{slug}'", is_new_project=True)

    # --- R1: a known project is mentioned ---
    matched = _match_known_project(haystack, known_projects)
    if matched:
        return RouteDecision(matched, note_type, f"mentions known project '{matched}'")

    # --- R3: undecided ---
    return RouteDecision("inbox", note_type, "no confident project match")
