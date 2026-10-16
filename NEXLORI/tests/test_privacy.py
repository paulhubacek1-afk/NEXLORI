import pytest

from nexlori.core.privacy import is_local_host, strip_tracking_params, tabs_to_sleep, upgrade_to_https


@pytest.mark.parametrize("url, expected", [
    ("https://example.org/a?utm_source=x&id=7&fbclid=abc", "https://example.org/a?id=7"),
    ("https://example.org/?utm_medium=mail", "https://example.org/"),
    ("https://example.org/a?b=2&a=1", "https://example.org/a?b=2&a=1"),             # nichts zu entfernen
    ("https://example.org/a?gclid=1#abschnitt", "https://example.org/a#abschnitt"),  # Fragment bleibt
    ("https://example.org/a?UTM_Campaign=x&q=hallo%20welt", "https://example.org/a?q=hallo%20welt"),
    ("https://example.org/a?ref=freund&utm_id=3", "https://example.org/a?ref=freund"),  # "ref" ist oft nötig
    ("mailto:a@b.c?utm_source=x", "mailto:a@b.c?utm_source=x"),
    ("about:blank", "about:blank"),
])
def test_strip_tracking_params(url, expected):
    assert strip_tracking_params(url) == expected


@pytest.mark.parametrize("url, expected", [
    ("http://example.org/a?b=1#c", "https://example.org/a?b=1#c"),
    ("http://example.org:80/", "https://example.org/"),
    ("http://example.org:8080/", None),             # Sonderport
    ("https://example.org/", None),                 # schon https
    ("http://localhost/", None),
    ("http://127.0.0.1:3000/", None),
    ("http://192.168.1.10/", None),
    ("http://nas/", None),                           # Intranet-Name ohne Punkt
    ("http://drucker.local/", None),
    ("http://user:pw@example.org/", None),
    ("ftp://example.org/", None),
])
def test_upgrade_to_https(url, expected):
    assert upgrade_to_https(url) == expected


def test_local_hosts():
    assert is_local_host("localhost") and is_local_host("10.0.0.5") and is_local_host("[::1]")
    assert not is_local_host("example.org") and not is_local_host("8.8.8.8")


def test_tabs_to_sleep_respects_limit_and_exclusions():
    last = {"a": 0.0, "b": 100.0, "c": 3000.0, "d": 10.0}
    assert sorted(tabs_to_sleep(last, now=1000.0, minutes=15)) == ["a", "b", "d"]  # 900 s Grenze
    assert tabs_to_sleep(last, now=1000.0, minutes=15, exclude={"a", "d"}) == ["b"]
    assert tabs_to_sleep(last, now=1000.0, minutes=0) == ["a", "b", "d"]            # mindestens 1 Minute
    assert tabs_to_sleep({}, now=1.0, minutes=5) == []
