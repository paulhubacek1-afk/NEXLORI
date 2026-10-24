from nexlori.core.themes import BUILTIN_THEMES
from nexlori.web_safety import error_page_html, is_nsfw_url


def test_nsfw_filter_runs_without_errors_on_normal_urls():
    # Bis 1.3 überschrieb eine zweite, kaputte Definition die Funktion (NameError bei jedem Aufruf).
    for url in ("https://example.com/", "https://de.wikipedia.org/wiki/Browser", "http://192.168.0.1", "not a url", ""):
        assert is_nsfw_url(url) is False


def test_blocked_page_is_rendered():
    page = error_page_html(BUILTIN_THEMES["dunkel"], "blocked", "https://blocked.example/")
    assert "Nexlori hat diese Adresse blockiert" in page
    assert "nexlori://browser/home" in page
