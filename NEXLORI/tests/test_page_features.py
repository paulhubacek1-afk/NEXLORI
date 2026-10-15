from nexlori.page_features import build_cookie_banner_script, clean_tracking_url


def test_tracking_cleaner_removes_common_parameters_and_keeps_real_query():
    target = clean_tracking_url(
        "https://example.com/article?utm_source=news&keep=yes&FBCLID=abc&gclid=123#heading"
    )
    assert target == "https://example.com/article?keep=yes#heading"


def test_tracking_cleaner_keeps_non_tracking_parameters_and_non_web_schemes():
    assert clean_tracking_url("https://example.com/?id=10&lang=de") == "https://example.com/?id=10&lang=de"
    assert clean_tracking_url("mailto:hello@example.com?utm_source=x") == "mailto:hello@example.com?utm_source=x"
    assert clean_tracking_url("not a url") == "not a url"


def test_cookie_banner_helper_only_targets_explicit_opt_out_labels():
    script = build_cookie_banner_script(True)
    assert "Alle ablehnen" in script
    assert "Only necessary" in script
    assert "rejectLabel.test(label)" in script
    assert "el.click()" in script
    assert "Accept all" not in script
    assert "remove()" not in script


def test_cookie_banner_helper_can_be_disabled():
    enabled = build_cookie_banner_script(True)
    disabled = build_cookie_banner_script(False)
    assert "state.enabled = true" in enabled
    assert "state.enabled = false" in disabled
