"""Auto-extraction of temporal facts from note content.

v0.8.1: Scans text for technology mentions and relationship patterns,
automatically adds/updates facts in the Temporal Knowledge Graph.

No LLM required — uses curated regex patterns for common expressions.
"""
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

from obsidian_bridge.graph import TemporalKnowledgeGraph, Contradiction

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Patterns for auto-extraction
# ---------------------------------------------------------------------------

# Technology categories — enables auto-specializing generic "uses" predicate
TECH_CATEGORIES: dict[str, set[str]] = {
    "uses_framework": {
        "flutter", "react", "next.js", "nextjs", "vue", "svelte", "django", "flask",
        "fastapi", "express", "nestjs", "spring", "nuxt", "remix", "astro", "vite",
    },
    "uses_state": {
        "riverpod", "bloc", "provider", "getx",
        "redux", "zustand", "jotai", "recoil", "mobx",
    },
    "uses_language": {
        "python", "typescript", "javascript", "dart", "rust", "go", "kotlin", "swift",
        "ruby", "java", "elixir",
    },
    "uses_db": {
        "postgresql", "postgres", "mysql", "sqlite", "mongodb", "redis", "supabase",
        "firebase", "turso", "planetscale", "neon", "drizzle", "prisma",
    },
    "uses_auth": {
        "clerk", "auth0", "firebase auth", "supabase auth", "nextauth", "lucia",
        "keycloak", "cognito",
    },
    "deploys_to": {
        "vercel", "aws", "gcp", "docker", "kubernetes", "fly.io", "railway",
        "render", "heroku", "netlify", "cloudflare", "digitalocean",
        "testflight", "app store", "google play",
    },
    "uses_ai": {
        "openai", "gpt", "claude", "gemini", "whisper", "langchain", "chromadb",
        "pinecone", "weaviate", "qdrant", "ollama", "llama",
    },
    "uses_tool": {
        "obsidian", "telegram", "notion", "github", "vscode", "cursor",
        "sentry", "posthog", "mixpanel", "stripe", "lemon squeezy",
    },
    "uses_testing": {
        "jest", "vitest", "pytest", "playwright", "cypress",
    },
    "uses_css": {
        "tailwind", "tailwindcss", "styled-components", "emotion",
    },
}

# Flat set for quick lookup
KNOWN_TECH: set[str] = set()
for _techs in TECH_CATEGORIES.values():
    KNOWN_TECH.update(_techs)


def _categorize_tech(name: str) -> str:
    """Get the specific predicate for a technology.

    E.g.: 'turso' → 'uses_db', 'clerk' → 'uses_auth', 'flutter' → 'uses_framework'
    """
    name = name.lower()
    for predicate, techs in TECH_CATEGORIES.items():
        if name in techs:
            return predicate
    return "uses"

# Capture group for tech name: 1-3 word tokens (tech names are short)
_TECH_CAPTURE = r"[`\"']?([\w][\w\.\-]*(?:\s[\w\.\-]+)?)[`\"']?"

# Predicate patterns — what relationship does the tech have to the project?
PREDICATE_PATTERNS: list[tuple[re.Pattern, str, str]] = [
    # (pattern, predicate, group_for_tech) — group_for_tech: "subject" or "object"

    # "uses X", "using X", "use X"
    (re.compile(
        r"(?:использ(?:ует|уем|ую)|переш(?:ли|ёл|ел)\s+на|"
        r"use[sd]?|using|adopt(?:ed|ing)?|implement(?:ed|ing)?|integrat(?:ed|ing)?|"
        r"выбрали|chose|picked|selected)\s+"
        r"(?:the\s+)?(?:new\s+)?"
        + _TECH_CAPTURE,
        re.IGNORECASE,
    ), "uses", "object"),

    # "switched from X to Y", "migrated from X to Y", "replaced X with Y"
    (re.compile(
        r"(?:switch(?:ed)?\s+from|migrat(?:ed|ing)\s+from|"
        r"replaced?|заменили|мигрировали\s+с|перешли\s+с)\s+"
        + _TECH_CAPTURE + r"\s+"
        r"(?:to|with|на|→)\s+"
        + _TECH_CAPTURE,
        re.IGNORECASE,
    ), "migration", "both"),

    # "deployed to X", "hosting on X", "деплой на X"
    (re.compile(
        r"(?:deploy(?:ed|ing)?\s+(?:to|on)|"
        r"host(?:ed|ing)?\s+on|"
        r"деплой\s+на|деплоим\s+на|"
        r"running\s+on)\s+"
        + _TECH_CAPTURE,
        re.IGNORECASE,
    ), "deploys_to", "object"),

    # "auth via X", "authentication with X", "авторизация через X"
    (re.compile(
        r"(?:auth(?:entication|orization)?\s+(?:via|with|through|using)|"
        r"авториз(?:ация|ацию)\s+через|"
        r"аутентификац(?:ия|ию)\s+через)\s+"
        + _TECH_CAPTURE,
        re.IGNORECASE,
    ), "uses_auth", "object"),

    # "database: X", "db: X", "база данных: X", "хранилище: X"
    (re.compile(
        r"(?:database|db|storage|хранилище|база\s+данных)\s*"
        r"(?::|—|–|-|is|=)\s*"
        + _TECH_CAPTURE,
        re.IGNORECASE,
    ), "uses_db", "object"),

    # "written in X", "built with X", "stack: X"
    (re.compile(
        r"(?:written\s+in|built\s+with|powered\s+by|"
        r"stack\s*(?::|—|–|-|is)|"
        r"написан\s+на|сделан\s+на)\s+"
        + _TECH_CAPTURE,
        re.IGNORECASE,
    ), "uses_framework", "object"),

    # "вместо X", "instead of X" (indicates replacement)
    (re.compile(
        r"(?:вместо|instead\s+of|rather\s+than|not\s+using)\s+"
        + _TECH_CAPTURE,
        re.IGNORECASE,
    ), "replaced", "object"),
]


@dataclass
class ExtractedFact:
    """A fact extracted from text before validation."""
    subject: str
    predicate: str
    object: str
    confidence: float = 0.8
    source_text: str = ""  # the sentence that triggered extraction


@dataclass
class AutoFactReport:
    """Report of auto-extracted facts."""
    facts_added: list[dict] = field(default_factory=list)
    contradictions_found: list[Contradiction] = field(default_factory=list)
    facts_skipped: list[str] = field(default_factory=list)

    def to_markdown(self) -> str:
        if not self.facts_added and not self.contradictions_found:
            return ""

        lines = ["## 🧠 Auto-extracted Facts", ""]

        if self.facts_added:
            for f in self.facts_added:
                lines.append(f"- ✅ `{f['subject']}` **{f['predicate']}** `{f['object']}`")
            lines.append("")

        if self.contradictions_found:
            lines.append("### ⚠️ Contradictions Detected (auto-resolved)")
            for c in self.contradictions_found:
                lines.append(f"- {c.message}")
            lines.append("")

        return "\n".join(lines)


class FactExtractor:
    """Extract temporal facts from text content automatically.

    Called by create_note and ingest_source to automate KG updates.

    Flow:
    1. Scan text for technology mentions
    2. Match against predicate patterns
    3. Validate extracted tech names against KNOWN_TECH
    4. Add valid facts to Temporal KG
    5. Report contradictions
    """

    def __init__(self, vault_path: Path):
        self.vault = vault_path
        self.tkg = TemporalKnowledgeGraph(vault_path)

    def extract_and_apply(
        self,
        text: str,
        project: str,
        source_note: str = "",
        valid_from: str = "",
    ) -> AutoFactReport:
        """Extract facts from text and add to Temporal KG.

        Args:
            text: The content to scan
            project: Project slug (used as default subject)
            source_note: Path to the source note
            valid_from: Date override (default: today)
        """
        report = AutoFactReport()

        # Step 1: Extract candidate facts
        candidates = self._extract_candidates(text, project)

        if not candidates:
            return report

        logger.info(f"Auto-extract: {len(candidates)} candidate facts from {source_note or project}")

        # Step 2: Validate and add each fact
        for candidate in candidates:
            # Skip if object isn't a known technology
            if not self._is_known_tech(candidate.object):
                report.facts_skipped.append(
                    f"{candidate.subject} {candidate.predicate} {candidate.object} "
                    f"(unknown tech: '{candidate.object}')"
                )
                continue

            # Handle migration: from X to Y
            if candidate.predicate == "migration_from":
                # Invalidate old tech
                self.tkg.invalidate(
                    candidate.subject,
                    "uses",
                    candidate.object,
                    ended=valid_from,
                )
                continue

            # Add the fact
            fact, contradictions = self.tkg.add_fact(
                subject=candidate.subject,
                predicate=candidate.predicate,
                obj=candidate.object,
                valid_from=valid_from,
                source_note=source_note,
                confidence=candidate.confidence,
            )

            report.facts_added.append({
                "subject": fact.subject,
                "predicate": fact.predicate,
                "object": fact.object,
                "valid_from": fact.valid_from,
            })

            report.contradictions_found.extend(contradictions)

        if report.facts_added:
            logger.info(
                f"Auto-extract: {len(report.facts_added)} facts added, "
                f"{len(report.contradictions_found)} contradictions"
            )

        return report

    def _extract_candidates(self, text: str, default_subject: str) -> list[ExtractedFact]:
        """Extract candidate facts using regex patterns."""
        candidates = []

        # Split into sentences for context
        sentences = re.split(r'[.!?\n]+', text)

        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) < 10:
                continue

            for pattern, predicate, group_type in PREDICATE_PATTERNS:
                for match in pattern.finditer(sentence):
                    if group_type == "both" and match.lastindex and match.lastindex >= 2:
                        # Migration pattern: from X to Y
                        old_tech = self._clean_tech_name(match.group(1))
                        new_tech = self._clean_tech_name(match.group(2))

                        # Invalidate old
                        candidates.append(ExtractedFact(
                            subject=default_subject,
                            predicate="migration_from",
                            object=old_tech,
                            confidence=0.9,
                            source_text=sentence[:100],
                        ))
                        # Add new
                        candidates.append(ExtractedFact(
                            subject=default_subject,
                            predicate=_categorize_tech(new_tech),
                            object=new_tech,
                            confidence=0.9,
                            source_text=sentence[:100],
                        ))
                    elif group_type == "object" and match.lastindex and match.lastindex >= 1:
                        tech = self._clean_tech_name(match.group(1))
                        # Auto-specialize generic "uses" to category-specific predicate
                        actual_predicate = predicate
                        if predicate == "uses":
                            actual_predicate = _categorize_tech(tech)
                        candidates.append(ExtractedFact(
                            subject=default_subject,
                            predicate=actual_predicate,
                            object=tech,
                            confidence=0.8,
                            source_text=sentence[:100],
                        ))

        # Deduplicate
        seen = set()
        unique = []
        for c in candidates:
            key = (c.subject, c.predicate, c.object)
            if key not in seen:
                seen.add(key)
                unique.append(c)

        return unique

    @staticmethod
    def _clean_tech_name(raw: str) -> str:
        """Clean a captured tech name: lowercase, strip stop words.

        'Flutter and' → 'flutter'
        'Turso для' → 'turso'
        'Next.js' → 'next.js'
        """
        # Stop words that indicate end of tech name
        stop_words = {
            "and", "or", "for", "with", "to", "in", "on", "at", "by", "as",
            "the", "a", "an", "is", "are", "was", "were", "from",
            "для", "и", "на", "с", "в", "из", "от", "до", "по", "к",
            "вместо", "через", "при", "без",
        }

        name = raw.strip().lower()

        # Split and take tokens before first stop word
        tokens = name.split()
        cleaned_tokens = []
        for token in tokens:
            if token in stop_words:
                break
            cleaned_tokens.append(token)

        return " ".join(cleaned_tokens) if cleaned_tokens else name

    @staticmethod
    def _is_known_tech(name: str) -> bool:
        """Check if a name is a known technology."""
        name = name.lower().strip()

        # Direct match
        if name in KNOWN_TECH:
            return True

        # Fuzzy match — handle slight variations
        normalized = name.replace("-", "").replace(".", "").replace(" ", "")
        for tech in KNOWN_TECH:
            tech_norm = tech.replace("-", "").replace(".", "").replace(" ", "")
            if normalized == tech_norm:
                return True

        return False
