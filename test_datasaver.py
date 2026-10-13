from nexlori.core.datasaver import Action, DataSaver, ResourceType as R, SaverLevel, SavingsLedger, site_of

PAGE = "https://www.beispiel.at/start"


def test_site_of_handles_common_two_level_suffixes():
    assert site_of("www.beispiel.at") == "beispiel.at"
    assert site_of("shop.example.co.uk") == "example.co.uk"
    assert site_of("localhost") == "localhost"


def test_third_party_trackers_are_blocked_but_first_party_is_not():
    ds = DataSaver()
    assert ds.decide("https://www.google-analytics.com/a.js", R.SCRIPT, PAGE).action is Action.BLOCK
    assert ds.decide("https://stats.doubleclick.net/x", R.IMAGE, PAGE).reason == "Tracker"
    assert ds.decide("https://www.beispiel.at/app.js", R.SCRIPT, PAGE).action is Action.ALLOW
    assert ds.decide("https://www.google-analytics.com/a.js", R.SCRIPT, "https://www.google-analytics.com/").action is Action.ALLOW


def test_tracker_blocking_can_be_switched_off():
    assert DataSaver(block_trackers=False).decide("https://doubleclick.net/x", R.SCRIPT, PAGE).action is Action.ALLOW


def test_off_level_allows_everything():
    assert DataSaver(level=SaverLevel.OFF).decide("https://doubleclick.net/x", R.SCRIPT, PAGE).action is Action.ALLOW


def test_site_allowlist_overrides_all_rules():
    ds = DataSaver(level=SaverLevel.STRICT, site_allowlist={"beispiel.at"})
    assert ds.decide("https://doubleclick.net/x", R.SCRIPT, PAGE).action is Action.ALLOW


def test_prefetch_rules():
    normal, strict = DataSaver(), DataSaver(level=SaverLevel.STRICT)
    assert normal.decide("https://www.beispiel.at/next", R.PREFETCH, PAGE).action is Action.ALLOW
    assert normal.decide("https://fremd.example/next", R.PREFETCH, PAGE).action is Action.BLOCK
    assert strict.decide("https://www.beispiel.at/next", R.PREFETCH, PAGE).action is Action.BLOCK


def test_autoplay_is_blocked_by_default_but_user_initiated_media_is_fine():
    ds = DataSaver()
    assert ds.decide("https://www.beispiel.at/v.mp4", R.MEDIA, PAGE, autoplay=True).reason == "Automatische Wiedergabe"
    assert ds.decide("https://www.beispiel.at/v.mp4", R.MEDIA, PAGE, autoplay=False).action is Action.ALLOW
    assert DataSaver(autoplay_allowed=True).decide("https://www.beispiel.at/v.mp4", R.MEDIA, PAGE, autoplay=True).action is Action.ALLOW


def test_strict_degrades_images_and_blocks_third_party_scripts():
    ds = DataSaver(level=SaverLevel.STRICT)
    assert ds.decide("https://www.beispiel.at/a.jpg", R.IMAGE, PAGE).action is Action.DEGRADE
    assert ds.decide("https://cdn.fremd.example/lib.js", R.SCRIPT, PAGE).action is Action.BLOCK
    assert ds.decide("https://www.beispiel.at/lib.js", R.SCRIPT, PAGE).action is Action.ALLOW
    assert DataSaver().decide("https://cdn.fremd.example/lib.js", R.SCRIPT, PAGE).action is Action.ALLOW


def test_ledger_counts_only_measured_bytes():
    ds, ledger = DataSaver(), SavingsLedger()
    ledger.record(ds.decide("https://doubleclick.net/x", R.SCRIPT, PAGE), 2048)
    ledger.record(ds.decide("https://hotjar.com/y", R.SCRIPT, PAGE), None)
    ledger.record(ds.decide("https://www.beispiel.at/ok.js", R.SCRIPT, PAGE), 999_999)  # erlaubt -> zählt nicht
    assert (ledger.blocked_requests, ledger.measured_bytes, ledger.unmeasured_requests) == (2, 2048, 1)
    assert ledger.by_reason == {"Tracker": 2}
    assert "2.0 KB gemessen" in ledger.summary() and "unbekannt" in ledger.summary()
