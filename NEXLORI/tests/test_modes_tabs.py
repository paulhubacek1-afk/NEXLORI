from nexlori.core.modes import PROFILES, Mode, ModeController
from nexlori.core.tabs import TabManager


def test_profiles_get_stricter_and_gaming_mutes_notifications():
    assert PROFILES[Mode.NORMAL].animations and not PROFILES[Mode.NORMAL].notifications_muted
    for mode in (Mode.ECO, Mode.BATTERY, Mode.GAMING):
        assert not PROFILES[mode].animations and PROFILES[mode].autoplay_forced_off and PROFILES[mode].throttle_background
    assert PROFILES[Mode.GAMING].notifications_muted and not PROFILES[Mode.BATTERY].notifications_muted
    assert PROFILES[Mode.GAMING].tab_sleep_after_s < PROFILES[Mode.BATTERY].tab_sleep_after_s < PROFILES[Mode.ECO].tab_sleep_after_s < PROFILES[Mode.NORMAL].tab_sleep_after_s


def test_gaming_does_not_switch_mode_unless_opted_in():
    c = ModeController(Mode.ECO)
    c.on_gaming_change(True)
    assert c.mode is Mode.ECO


def test_gaming_switch_and_restore_to_previous_base_mode():
    seen = []
    c = ModeController(Mode.ECO, gaming_auto_switch=True)
    c.subscribe(seen.append)
    c.on_gaming_change(True)
    assert c.mode is Mode.GAMING and c.profile.notifications_muted
    c.on_gaming_change(True)  # keine doppelte Meldung
    c.on_gaming_change(False)
    assert c.mode is Mode.ECO and seen == [Mode.GAMING, Mode.ECO]


def test_no_auto_restore_stays_until_user_leaves():
    c = ModeController(gaming_auto_switch=True, auto_restore=False)
    c.on_gaming_change(True)
    c.on_gaming_change(False)
    assert c.mode is Mode.GAMING
    c.leave_gaming()
    assert c.mode is Mode.NORMAL


def test_changing_base_mode_notifies_only_on_effective_change():
    seen = []
    c = ModeController(gaming_auto_switch=True)
    c.subscribe(seen.append)
    c.on_gaming_change(True)
    c.set_base(Mode.BATTERY)  # Gaming überlagert -> effektiv keine Änderung
    assert seen == [Mode.GAMING] and c.base is Mode.BATTERY


def test_tabs_sleep_only_when_idle_and_not_protected():
    tm = TabManager()
    a = tm.open("https://a", 0)
    b = tm.open("https://b", 0, activate=False)
    pinned = tm.open("https://p", 0, activate=False)
    pinned.pinned = True
    loud = tm.open("https://m", 0, activate=False)
    loud.audible = True
    idle = tm.open("https://i", 0, activate=False)
    assert tm.active_id == a.id
    ids = {t.id for t in tm.plan_suspend(now=600, sleep_after_s=300)}
    assert ids == {b.id, idle.id}
    assert tm.plan_suspend(now=100, sleep_after_s=300) == []
    assert tm.plan_suspend(now=9999, sleep_after_s=None) == []


def test_apply_policy_and_wake_on_activate():
    from nexlori.core.modes import PROFILES

    tm = TabManager()
    tm.open("https://a", 0)
    b = tm.open("https://b", 0, activate=False)
    tm.update_measurements(b.id, 120.0, 3.0)
    assert tm.apply_policy(now=500, profile=PROFILES[Mode.ECO]) == [b.id]
    assert b.suspended and b.memory_mb is None
    tm.activate(b.id, now=501)
    assert not b.suspended


def test_active_tab_is_never_suspended_even_when_idle():
    tm = TabManager()
    a = tm.open("https://a", 0)
    assert tm.plan_suspend(now=10_000, sleep_after_s=60) == []
    assert tm.active_id == a.id


def test_resource_report_is_sorted_and_separates_unmeasured_tabs():
    tm = TabManager()
    a = tm.open("https://a", 0)
    b = tm.open("https://b", 0, activate=False)
    c = tm.open("https://c", 0, activate=False)
    tm.update_measurements(a.id, 50.0, 1.0)
    tm.update_measurements(b.id, 300.0, 9.0)
    report = tm.resource_report()
    assert [t.id for t in report.measured] == [b.id, a.id]
    assert [t.id for t in report.unmeasured] == [c.id]
    assert report.total_memory_mb == 350.0


def test_close_active_tab_picks_another():
    tm = TabManager()
    a = tm.open("https://a", 0)
    b = tm.open("https://b", 0, activate=False)
    tm.close(a.id)
    assert tm.active_id == b.id
    tm.close(b.id)
    assert tm.active_id is None
