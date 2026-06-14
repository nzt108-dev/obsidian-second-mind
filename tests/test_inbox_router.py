"""Tests for inbox_router — rule-based inbox classification."""

from obsidian_bridge.inbox_router import classify, _slugify_project

KNOWN = ["faithly", "botseller", "darshan", "flow", "crewup"]


def test_classify_spec_header_new_project_creates_slug():
    text = "ТЗ: KeyStack — локальная память ключей и стека для вайб-агентов (MVP)"
    d = classify(text, title=text, known_projects=KNOWN)
    assert d.project == "keystack"
    assert d.is_new_project is True


def test_classify_spec_header_existing_project_routes_to_it():
    text = "ТЗ: Faithly — добавить поиск служителей по городу, экран фильтров"
    d = classify(text, title=text, known_projects=KNOWN)
    assert d.project == "faithly"
    assert d.is_new_project is False


def test_classify_proekt_nazyvaetsya_pattern_new_project():
    text = "Идея на вечер. Проект называется Spotlight, делаем агрегатор подкастов и фид."
    d = classify(text, known_projects=KNOWN)
    assert d.project == "spotlight"
    assert d.is_new_project is True


def test_classify_known_project_mention_routes_to_it():
    text = "Надо в botseller добавить вебхук на оплату и пересчитать тарифы COMMUNITY."
    d = classify(text, known_projects=KNOWN)
    assert d.project == "botseller"
    assert d.is_new_project is False


def test_classify_plain_idea_stays_in_inbox():
    text = "Купить молоко и посмотреть документалку про океан на выходных как-нибудь."
    d = classify(text, known_projects=KNOWN)
    assert d.project == "inbox"


def test_classify_empty_text_stays_in_inbox():
    assert classify("", known_projects=KNOWN).project == "inbox"


def test_classify_too_short_text_stays_in_inbox():
    assert classify("ok", known_projects=KNOWN).project == "inbox"


def test_classify_tie_between_two_projects_stays_in_inbox():
    # faithly and darshan mentioned exactly once each → tie → undecided
    text = "Сравнить онбординг в faithly и darshan, выписать различия по экранам входа."
    d = classify(text, known_projects=KNOWN)
    assert d.project == "inbox"


def test_classify_url_sets_research_type():
    text = "Полезная статья про память агентов https://example.com/agent-memory почитать."
    d = classify(text, known_projects=KNOWN)
    assert d.note_type == "research"


def test_classify_does_not_match_short_project_name_in_prose():
    # "flow" (len 4 is allowed) — use a <4 char hypothetical to confirm guard;
    # here ensure a generic word doesn't pull a project when not named.
    text = "Сегодня был хороший рабочий поток и продуктивный день, без привязки к делу."
    d = classify(text, known_projects=KNOWN + ["ai"])
    assert d.project == "inbox"  # "ai" too short, "поток" != "flow"


def test_classify_generic_bucket_word_does_not_route():
    # A note about "research" must NOT land in a folder literally named research.
    text = "Полезный research про маркетинговые агенты для SEO и роста аудитории."
    d = classify(text, known_projects=KNOWN + ["research"])
    assert d.project == "inbox"


def test_slugify_non_ascii_returns_empty():
    assert _slugify_project("Имя") == ""


def test_slugify_camelcase_lowercased_with_dash():
    assert _slugify_project("KeyStack") == "keystack"
    assert _slugify_project("Auto Transport") == "auto-transport"
