from nexlori.core.gaming import EXAMPLE_GAME_PROCESSES, GamingDetector


class Source:
    def __init__(self, names=()):
        self.names, self.calls = list(names), 0

    def __call__(self):
        self.calls += 1
        return self.names


def test_disabled_by_default_and_never_reads_processes():
    src = Source(["cs2.exe"])
    det = GamingDetector(src)
    assert not det.enabled and det.poll() is False and src.calls == 0


def test_enter_needs_consecutive_hits_and_exit_needs_consecutive_misses():
    src, events = Source(["cs2.exe"]), []
    det = GamingDetector(src, enabled=True, enter_after=2, exit_after=3)
    det.subscribe(events.append)
    assert det.poll() is False and det.poll() is True
    src.names = []
    assert det.poll() is True and det.poll() is True and det.poll() is False
    assert events == [True, False]


def test_flicker_does_not_trigger_changes():
    src, events = Source(["cs2.exe"]), []
    det = GamingDetector(src, enabled=True, enter_after=2)
    det.subscribe(events.append)
    det.poll()
    src.names = []
    det.poll()
    src.names = ["cs2.exe"]
    det.poll()
    assert events == []


def test_matching_is_case_insensitive_and_custom_names_work():
    det = GamingDetector(Source(["MeinSpiel.EXE", "firefox.exe"]), game_names=["meinspiel.exe"], enabled=True, enter_after=1)
    assert det.poll() is True


def test_non_game_processes_are_ignored():
    det = GamingDetector(Source(["chrome.exe", "code.exe"]), enabled=True, enter_after=1)
    assert det.poll() is False


def test_disable_resets_state_and_notifies_once():
    src, events = Source(["cs2.exe"]), []
    det = GamingDetector(src, enabled=True, enter_after=1)
    det.subscribe(events.append)
    det.poll()
    det.disable()
    assert events == [True, False] and not det.active
    calls = src.calls
    det.poll()
    assert src.calls == calls  # nach dem Abschalten wird nichts mehr gelesen


def test_example_list_is_lowercase_for_matching():
    assert all(n == n.lower() for n in EXAMPLE_GAME_PROCESSES)


def test_psutil_source_returns_process_names_when_available():
    pytest = __import__("pytest")
    pytest.importorskip("psutil")
    from nexlori.core.gaming import psutil_process_source

    names = list(psutil_process_source()())
    assert names and all(isinstance(n, str) for n in names)
