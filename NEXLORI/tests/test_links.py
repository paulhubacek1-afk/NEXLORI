import re

from nexlori.links import DISCORD_URL, PROJECT_LINKS
from nexlori.start_page import build_start_page as _start_page
from nexlori.web_safety import addons_page_html
from nexlori.core.themes import BUILTIN_THEMES


def test_discord_invite_link_is_fixed_and_https():
    assert DISCORD_URL == "https://discord.com/invite/KM5m7s9GyK"
    assert re.fullmatch(r"https://discord\.com/invite/[A-Za-z0-9]+", DISCORD_URL)


def test_addons_page_links_builtin_addons():
    page = addons_page_html(BUILTIN_THEMES["dunkel"])
    assert "nexlori://addons/builtin" in page and "nexlori://addons/install-zip" in page


def test_project_links_are_https_and_labeled():
    assert len(PROJECT_LINKS) >= 5
    assert all(item["url"].startswith("https://") and item["title"] for item in PROJECT_LINKS)


def test_start_page_shows_bookmarks_below_search_and_escapes_titles():
    html = _start_page(
        BUILTIN_THEMES["dunkel"],
        "https://duckduckgo.com/?q={}",
        bookmarks=[{"title": "<script>example</script>", "url": "https://example.com"}],
    )
    assert 'id="search"' in html
    assert 'class="bookmarks-section"' in html
    assert 'href="https://example.com"' in html
    assert "&lt;script&gt;example&lt;/script&gt;" in html
    assert "<script>example</script>" not in html
    assert "Meine Online-Projekte" in html
