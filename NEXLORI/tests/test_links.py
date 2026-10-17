import re

from nexlori.links import DISCORD_URL
from nexlori.web_safety import addons_page_html
from nexlori.core.themes import BUILTIN_THEMES


def test_discord_invite_link_is_fixed_and_https():
    assert DISCORD_URL == "https://discord.com/invite/KM5m7s9GyK"
    assert re.fullmatch(r"https://discord\.com/invite/[A-Za-z0-9]+", DISCORD_URL)


def test_addons_page_links_builtin_addons():
    page = addons_page_html(BUILTIN_THEMES["dunkel"])
    assert "nexlori://addons/builtin" in page and "nexlori://addons/install-zip" in page
