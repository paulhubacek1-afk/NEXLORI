import json

import pytest

from nexlori.core.adblock import (
    BUILTIN_DOMAINS, COSMETIC_SELECTORS, FILTER_LISTS, AdBlocker, FilterListError, FilterListStore,
    build_cosmetic_script, cosmetic_css, download_filter_list, parse_filter_list,
)


def test_known_ad_and_tracker_requests_are_blocked():
    blocker = AdBlocker()
    assert blocker.should_block("https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js", "https://news.example/")
    assert blocker.should_block("https://securepubads.g.doubleclick.net/tag/js/gpt.js", "https://news.example/")
    assert blocker.should_block("https://www.google-analytics.com/analytics.js", "https://shop.example/")
    assert blocker.should_block("https://connect.facebook.net/en_US/fbevents.js", "https://shop.example/")


def test_normal_content_is_not_blocked():
    blocker = AdBlocker()
    assert not blocker.should_block("https://cdn.example.com/app.js", "https://example.com/")
    assert not blocker.should_block("https://i.ytimg.com/vi/abc/hqdefault.jpg", "https://www.youtube.com/watch?v=abc")
    assert not blocker.should_block("https://www.youtube.com/s/player/base.js", "https://www.youtube.com/")
    assert not blocker.should_block("data:image/png;base64,AAAA", "https://example.com/")


def test_youtube_ad_endpoints_are_blocked_by_path_rules_even_first_party():
    blocker = AdBlocker()
    assert blocker.should_block("https://www.youtube.com/api/stats/ads?ver=2", "https://www.youtube.com/watch?v=1")
    assert blocker.should_block("https://www.youtube.com/pagead/adview?x=1", "https://www.youtube.com/")


def test_path_rules_from_domain_list():
    blocker = AdBlocker()
    assert blocker.should_block("https://yandex.ru/metrika/tag.js", "https://example.ru/")
    assert not blocker.should_block("https://yandex.ru/search/?text=x", "https://example.ru/")


def test_path_rules_do_not_block_unrelated_paths_with_same_prefix():
    blocker = AdBlocker()
    assert blocker.should_block("https://www.facebook.com/tr", "https://news.example/")
    assert blocker.should_block("https://www.facebook.com/tr/events", "https://news.example/")
    assert not blocker.should_block("https://www.facebook.com/travel/story", "https://news.example/")


def test_listed_site_may_load_its_own_files_when_opened_directly():
    blocker = AdBlocker()
    assert not blocker.should_block("https://www.taboola.com/static/site.css", "https://www.taboola.com/")
    assert blocker.should_block("https://cdn.taboola.com/libtrc/loader.js", "https://news.example/")


def test_allowlist_pauses_blocking_for_a_site_and_its_subdomains():
    blocker = AdBlocker(allowlist=["example.com"])
    ad = "https://pagead2.googlesyndication.com/x.js"
    assert not blocker.should_block(ad, "https://www.example.com/article")
    assert blocker.should_block(ad, "https://other.example/")
    blocker.set_allowlist([])
    assert blocker.should_block(ad, "https://www.example.com/article")


def test_disabled_blocker_never_blocks():
    blocker = AdBlocker(enabled=False)
    assert not blocker.should_block("https://doubleclick.net/x", "https://a.example/")
    blocker.set_enabled(True)
    assert blocker.should_block("https://doubleclick.net/x", "https://a.example/")


def test_statistics_are_counted_per_site():
    blocker = AdBlocker()
    for _ in range(3):
        blocker.should_block("https://doubleclick.net/x", "https://www.news.example/")
    blocker.should_block("https://doubleclick.net/x", "https://other.example/")
    assert blocker.blocked_for_site("www.news.example") == 3
    assert blocker.blocked_total == 4
    blocker.reset_site("www.news.example")
    assert blocker.blocked_for_site("www.news.example") == 0


def test_extra_domains_from_filter_lists_are_used():
    blocker = AdBlocker(extra_domains=["ads.custom-network.example"])
    assert blocker.should_block("https://x.ads.custom-network.example/a.js", "https://site.example/")
    blocker.set_extra_domains([])
    assert not blocker.should_block("https://x.ads.custom-network.example/a.js", "https://site.example/")
    assert blocker.domain_count == len(BUILTIN_DOMAINS)


def test_filter_list_parser_accepts_hosts_plain_and_adblock_domain_rules():
    text = """
# comment
! adblock comment
[Adblock Plus 2.0]
0.0.0.0 ads.one.example
127.0.0.1 tracker.two.example # trailing comment
127.0.0.1 localhost
0.0.0.0 0.0.0.0
plain.three.example
||four.example^
||path.example/ads^
||wild*.example^
not a domain line
0.0.0.0 github.com
"""
    assert parse_filter_list(text) == {
        "ads.one.example", "tracker.two.example", "plain.three.example", "four.example",
    }


def test_filter_store_roundtrip_and_refresh(tmp_path):
    store = FilterListStore(tmp_path)
    assert store.needs_refresh(["pgl"], now=1000.0) == ["pgl"]
    store.store("pgl", {"ads.a.example", "ads.b.example"}, now=1000.0)
    assert store.domains(["pgl"]) == {"ads.a.example", "ads.b.example"}
    assert store.info()["pgl"]["count"] == 2
    assert store.needs_refresh(["pgl"], now=1000.0 + 3600) == []
    assert store.needs_refresh(["pgl"], now=1000.0 + 5 * 24 * 3600) == ["pgl"]
    with pytest.raises(FilterListError):
        store.store("unknown", set())


def test_filter_store_ignores_tampered_entries(tmp_path):
    store = FilterListStore(tmp_path)
    store.path.write_text(json.dumps({"pgl": {"fetched": 1, "domains": ["ok.example", "bad domain", "github.com", 5]}}))
    assert store.domains(["pgl"]) == {"ok.example"}
    store.path.write_text("not json")
    assert store.domains(["pgl"]) == set()


def test_filter_store_handles_invalid_fetch_timestamp_and_sanitizes_domains(tmp_path):
    store = FilterListStore(tmp_path)
    store.path.write_text(json.dumps({
        "pgl": {"fetched": "not-a-number", "domains": ["good.example"]}
    }), encoding="utf-8")
    assert store.info()["pgl"]["fetched"] == 0
    assert store.needs_refresh(["pgl"], now=1000.0) == ["pgl"]

    store.store("pgl", {"good.example", "github.com", "not a domain", "also-good.example"})
    assert store.domains(["pgl"]) == {"good.example", "also-good.example"}


def test_download_rejects_tiny_or_unknown_lists(monkeypatch):
    class FakeResponse:
        def __init__(self, payload):
            self.payload = payload

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self, _size):
            return self.payload

    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: FakeResponse(b"0.0.0.0 ads.example\n"))
    with pytest.raises(FilterListError, match="wenige"):
        download_filter_list("pgl")
    big = "\n".join(f"0.0.0.0 ads{i}.example" for i in range(100)).encode()
    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: FakeResponse(big))
    assert len(download_filter_list("pgl")) == 100
    with pytest.raises(FilterListError):
        download_filter_list("evil")


def test_filter_list_sources_are_https_and_one_is_default():
    assert all(item.url.startswith("https://") for item in FILTER_LISTS)
    assert [item.id for item in FILTER_LISTS if item.default] == ["pgl"]


def test_cosmetic_script_hides_ads_and_respects_allowlist():
    css = cosmetic_css()
    assert "ins.adsbygoogle" in css and "display: none !important" in css
    assert "ytd-ad-slot-renderer" in COSMETIC_SELECTORS
    script = build_cosmetic_script(allowlisted_hosts=["Example.COM"])
    assert '"example.com"' in script
    assert "ytp-ad-skip-button" in script
    assert "__nexloriShield" in script
    assert "const start = () =>" in script
    assert "start();" in script
    assert "new MutationObserver(skip).observe(root" in script
