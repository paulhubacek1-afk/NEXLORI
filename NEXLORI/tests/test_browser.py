import pytest

from nexlori.browser import BrowserSession, History, load_page, normalize_input, resolve_link
from nexlori.core.modes import Mode
from nexlori.core.settings import Settings
from nexlori.net import FetchError, FetchResult

SEARCH = Settings().search_url


# ------------------------------------------------------------------ Adresseingabe
@pytest.mark.parametrize(
    "text, expected",
    [
        ("example.org", "https://example.org"),
        ("  example.org/pfad?q=1 ", "https://example.org/pfad?q=1"),
        ("localhost:8000/x", "http://localhost:8000/x"),
        ("192.168.0.1/admin", "http://192.168.0.1/admin"),
        ("8.8.8.8", "https://8.8.8.8"),
        ("http://a.b/c", "http://a.b/c"),
        ("wien wetter", "https://duckduckgo.com/?q=wien+wetter"),
        ("wien", "https://duckduckgo.com/?q=wien"),
        ("äpfel & birnen", "https://duckduckgo.com/?q=%C3%A4pfel+%26+birnen"),
        ("", "about:blank"),
        ("ABOUT:Start", "about:start"),
        ("javascript:alert(1)", "javascript:alert(1)"),
    ],
)
def test_normalize_input(text, expected):
    assert normalize_input(text, SEARCH) == expected


def test_normalize_input_recognizes_existing_local_files(tmp_path):
    f = tmp_path / "a.html"
    f.write_text("<p>x</p>", encoding="utf-8")
    assert normalize_input(str(f), SEARCH) == f.resolve().as_uri()
    assert normalize_input(str(tmp_path / "gibt-es-nicht.html"), SEARCH).startswith("https://")


# ------------------------------------------------------------------ Links
def test_resolve_link_variants():
    base = "https://example.org/a/b.html"
    assert resolve_link(base, "c.html") == "https://example.org/a/c.html"
    assert resolve_link(base, "/x?y=1#z") == "https://example.org/x?y=1"
    assert resolve_link(base, "//cdn.example.org/p") == "https://cdn.example.org/p"
    assert resolve_link(base, "#oben") is None
    assert resolve_link(base, "") is None


def test_dangerous_link_targets_are_blocked():
    web = "https://example.org/"
    for href in ("javascript:alert(1)", "mailto:a@b.c", "data:text/html,x", "file:///etc/passwd", "about:start", "ftp://x/y"):
        assert resolve_link(web, href) is None, href
    assert resolve_link("about:start", "about:test") == "about:test"
    assert resolve_link("about:start", "https://example.org/") == "https://example.org/"
    assert resolve_link("file:///tmp/a.html", "b.html") == "file:///tmp/b.html"


# ------------------------------------------------------------------ Seiten laden
def test_internal_pages():
    start = load_page("about:start")
    assert start.title == "Nexlori" and not start.error and start.document is not None
    assert load_page("ABOUT:TEST").title == "Nexlori Testseite"
    assert load_page("about:blank").document is not None
    missing = load_page("about:gibtsnicht")
    assert missing.error and "gibt es nicht" in missing.note


def test_unsupported_schemes_become_error_pages():
    for url in ("javascript:alert(1)", "ftp://example.com/", "data:text/html,x", "gopher://x"):
        page = load_page(url)
        assert page.error and "nicht unterstützt" in page.note, url
        assert page.document.title == "Fehler"


def test_web_pages_use_the_fetcher_and_report_status_and_truncation():
    seen = []

    def fake(url):
        seen.append(url)
        return FetchResult("https://example.org/final", 200, "text/html", "<title>Titel</title><p>x</p>", truncated=True)

    page = load_page("https://example.org/start", fake)
    assert seen == ["https://example.org/start"]
    assert (page.url, page.title, page.status) == ("https://example.org/final", "Titel", 200)
    assert "gekürzt" in page.note and not page.error


def test_plain_text_responses_keep_line_breaks_and_escape_markup():
    page = load_page("https://x.y/", lambda u: FetchResult(u, 200, "text/plain", "a<b>\nzweite", False))
    assert "a<b>" in page.document.dom.text_content()
    assert not page.document.dom.find_all("b")
    assert len(page.document.dom.find_all("br")) == 1


def test_fetch_errors_and_crashes_become_error_pages_not_exceptions():
    def boom(url):
        raise FetchError("Der Server ist nicht erreichbar (test).")

    page = load_page("https://x.y/", boom)
    assert page.error and "nicht erreichbar" in page.note and "x.y" in page.document.dom.text_content()

    def crash(url):
        raise ValueError("kaputt")

    assert "ValueError" in load_page("https://x.y/", crash).note


def test_missing_title_falls_back_to_url():
    page = load_page("https://x.y/", lambda u: FetchResult(u, 200, "text/html", "<p>x</p>", False))
    assert page.title == "https://x.y/"


def test_deeply_nested_page_does_not_crash():
    html = "<div>" * 3000 + "x" + "</div>" * 3000
    page = load_page("https://x.y/", lambda u: FetchResult(u, 200, "text/html", html, False))
    assert page.document is not None or page.error  # entweder dargestellt oder als Fehlerseite gemeldet


def test_local_files(tmp_path):
    html = tmp_path / "a.html"
    html.write_text("<title>Lokal</title><p>ä</p>", encoding="utf-8")
    page = load_page(html.resolve().as_uri())
    assert page.title == "Lokal" and not page.error
    txt = tmp_path / "n.txt"
    txt.write_text("eins\nzwei", encoding="utf-8")
    assert len(load_page(txt.resolve().as_uri()).document.dom.find_all("br")) == 1
    exe = tmp_path / "x.exe"
    exe.write_bytes(b"MZ")
    assert load_page(exe.resolve().as_uri()).error
    assert load_page((tmp_path / "nix.html").resolve().as_uri()).error
    assert load_page("file://server/share/x.html").error  # Netzwerkpfade nicht laden


# ------------------------------------------------------------------ Verlauf / Sitzung
def test_history_back_forward_and_truncation():
    h = History()
    for u in ("a", "b", "c"):
        h.visit(u)
    assert (h.current, h.can_back, h.can_forward) == ("c", True, False)
    assert h.back() == "b" and h.back() == "a" and h.back() is None
    assert h.forward() == "b"
    h.visit("x")  # verwirft „c“
    assert h.entries == ["a", "b", "x"] and not h.can_forward
    h.replace("y")
    assert h.entries == ["a", "b", "y"]


def test_history_limit():
    h = History(limit=3)
    for u in "abcde":
        h.visit(u)
    assert h.entries == ["c", "d", "e"] and h.current == "e"


def test_session_tabs_commit_and_navigation():
    s = BrowserSession()
    t1 = s.open_tab(0)
    s.commit(t1, "about:start")
    s.commit(t1, "https://example.org/")
    assert s.tabs.tabs[t1].url == "https://example.org/"
    assert s.go_back(t1) == "about:start" and s.go_forward(t1) == "https://example.org/"
    s.commit(t1, "https://example.org/neu", push=False)  # Reload/Weiterleitung ersetzt nur
    assert s.history[t1].entries == ["about:start", "https://example.org/neu"]
    t2 = s.open_tab(1, activate=False)
    assert s.tabs.active_id == t1
    s.close_tab(t1)
    assert s.tabs.active_id == t2 and t1 not in s.history
    assert s.resolve_input("abc def").startswith("https://duckduckgo.com/")


def test_session_sleep_policy_follows_mode_and_gaming():
    s = BrowserSession(Settings(mode="eco", gaming_auto_switch=True))
    a, b = s.open_tab(0), s.open_tab(0, activate=False)
    assert s.tick(100) == []  # ECO: nach 300 s
    assert s.tick(301) == [b]
    assert s.tabs.tabs[b].suspended and not s.tabs.tabs[a].suspended
    s.tabs.activate(b, 302)
    assert not s.tabs.tabs[b].suspended
    s.modes.on_gaming_change(True)
    assert s.modes.mode is Mode.GAMING
    assert s.tick(302 + 61) == [a]  # Gaming: nach 60 s


def test_settings_validation_for_new_fields():
    with pytest.raises(ValueError, match="search_url"):
        Settings.from_dict({"search_url": "http://unsicher.example/?q={}"})
    with pytest.raises(ValueError, match="search_url"):
        Settings.from_dict({"search_url": "https://x.example/?q="})
    with pytest.raises(ValueError, match="page_zoom"):
        Settings.from_dict({"page_zoom": 9})
    assert Settings.from_dict({"page_zoom": 1.5}).page_zoom == 1.5
