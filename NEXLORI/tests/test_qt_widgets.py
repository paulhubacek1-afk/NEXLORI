"""Tests für die Oberflächen-Bausteine ohne Webengine (laufen offscreen; werden übersprungen, wenn Qt fehlt)."""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6.QtWidgets")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtGui import QColor, QImage  # noqa: E402
from PySide6.QtWidgets import QApplication, QLabel, QWidget  # noqa: E402

from nexlori.animations import AccentLine, Motion  # noqa: E402
from nexlori.core.themes import BUILTIN_THEMES  # noqa: E402
from nexlori.tabstrip import TabStrip  # noqa: E402
from nexlori.titlebar import RESIZE_MARGIN, ResizeFrame, TitleBar, apply_native_titlebar_colors, colorref  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def page(name: str) -> QWidget:
    widget = QLabel(name)
    widget.setObjectName(name)
    return widget


# ------------------------------------------------------------------ TabStrip
def test_tabstrip_keeps_bar_and_stack_in_sync(app):
    tabs = TabStrip()
    seen = []
    tabs.currentChanged.connect(seen.append)
    pages = [page(n) for n in ("a", "b", "c")]
    for p in pages:
        tabs.addTab(p, p.objectName())
    assert tabs.count() == 3 and tabs.stack.count() == 3
    assert tabs.currentWidget() is pages[0] and seen[0] == 0
    tabs.setCurrentIndex(2)
    assert tabs.currentWidget() is pages[2] and tabs.stack.currentWidget() is pages[2]
    assert [tabs.indexOf(p) for p in pages] == [0, 1, 2]


def test_tabstrip_reorders_stack_when_tab_is_dragged(app):
    tabs = TabStrip()
    pages = [page(n) for n in ("a", "b", "c")]
    for p in pages:
        tabs.addTab(p, p.objectName())
    tabs.setCurrentIndex(0)
    tabs.bar.moveTab(0, 2)
    assert [tabs.widget(i).objectName() for i in range(3)] == ["b", "c", "a"]
    assert tabs.currentWidget() is pages[0]                  # aktiver Tab bleibt aktiv
    assert tabs.bar.tabText(2) == "a"


def test_tabstrip_remove_selects_neighbour_and_keeps_order(app):
    tabs = TabStrip()
    pages = [page(n) for n in ("a", "b", "c")]
    for p in pages:
        tabs.addTab(p, p.objectName())
    tabs.setCurrentIndex(1)
    tabs.removeTab(1)
    assert tabs.count() == 2 and tabs.stack.count() == 2
    assert tabs.currentWidget() in (pages[0], pages[2])
    assert tabs.currentIndex() == tabs.stack.currentIndex()
    tabs.removeTab(0)
    tabs.removeTab(0)
    assert tabs.count() == 0 and tabs.currentWidget() is None


def test_tabstrip_text_and_close_signal(app):
    tabs = TabStrip()
    closed = []
    tabs.tabCloseRequested.connect(closed.append)
    tabs.addTab(page("a"), "Titel")
    tabs.setTabText(0, "Neu")
    assert tabs.tabText(0) == "Neu"
    tabs.bar.tabCloseRequested.emit(0)
    assert closed == [0]


# ------------------------------------------------------------------ Titelleiste & Größenänderung
def test_titlebar_state_and_elided_title(app):
    host = QWidget()
    bar = TitleBar(host)
    bar.resize(500, 38)
    bar.set_title("x" * 300)
    assert len(bar.title_label.text()) < 300 and bar.title_label.toolTip() == "x" * 300
    bar.set_maximized(True)
    assert bar.max_button.text() == "❐"
    bar.set_maximized(False)
    assert bar.max_button.text() == "☐"
    assert {b.objectName() for b in (bar.min_button, bar.max_button, bar.close_button)} == {"titleButton", "titleCloseButton"}


def test_resize_frame_edges_and_cursors(app):
    host = QWidget()
    frame = ResizeFrame(host, QWidget())
    frame.resize(800, 600)
    m = RESIZE_MARGIN
    assert frame._edges_at(400, 300) == Qt.Edge(0)                                   # Mitte: nichts
    assert frame._edges_at(1, 300) == Qt.Edge.LeftEdge
    assert frame._edges_at(799, 300) == Qt.Edge.RightEdge
    assert frame._edges_at(400, 1) == Qt.Edge.TopEdge
    assert frame._edges_at(400, 599) == Qt.Edge.BottomEdge
    assert frame._edges_at(1, 1) == Qt.Edge.LeftEdge | Qt.Edge.TopEdge
    assert frame._edges_at(799, 599) == Qt.Edge.RightEdge | Qt.Edge.BottomEdge
    assert frame._edges_at(m * 2, 1) == Qt.Edge.LeftEdge | Qt.Edge.TopEdge           # großzügige Ecke
    assert frame.cursor_for(Qt.Edge.LeftEdge) == Qt.CursorShape.SizeHorCursor
    assert frame.cursor_for(Qt.Edge.TopEdge) == Qt.CursorShape.SizeVerCursor
    assert frame.cursor_for(Qt.Edge.LeftEdge | Qt.Edge.TopEdge) == Qt.CursorShape.SizeFDiagCursor
    assert frame.cursor_for(Qt.Edge.RightEdge | Qt.Edge.TopEdge) == Qt.CursorShape.SizeBDiagCursor
    assert frame.cursor_for(Qt.Edge(0)) is None


def test_resize_frame_is_not_resizable_when_maximized(app):
    host = QWidget()
    frame = ResizeFrame(host, QWidget())
    frame.resize(800, 600)
    frame.set_resizable(False)
    assert frame._edges_at(1, 1) == Qt.Edge(0)
    margins = frame.layout().contentsMargins()
    assert (margins.left(), margins.top(), margins.right(), margins.bottom()) == (0, 0, 0, 0)
    frame.set_resizable(True)
    assert frame.layout().contentsMargins().left() == RESIZE_MARGIN


def test_colorref_and_native_titlebar_noop_on_other_platforms(app):
    assert colorref("#FF0000") == 0x0000FF          # Windows erwartet 0x00BBGGRR
    assert colorref("#00FF00") == 0x00FF00
    assert colorref("#0000FF") == 0xFF0000
    import sys
    if sys.platform != "win32":
        assert apply_native_titlebar_colors(QWidget(), BUILTIN_THEMES["dunkel"]) is False


# ------------------------------------------------------------------ Animationen
def test_motion_levels():
    assert Motion("full").ms(200) == 200 and Motion("full").continuous
    assert Motion("reduced").ms(200) == 100 and not Motion("reduced").continuous and Motion("reduced").enabled
    assert Motion("off").ms(200) == 0 and not Motion("off").enabled
    assert Motion("unsinn").mode == "full"


def _pixel(line: AccentLine, x: int):
    image = QImage(line.size(), QImage.Format.Format_ARGB32)
    line.render(image)
    return image.pixelColor(x, 1)


def _close(color, hex_value, tolerance=8):
    expected = QColor(hex_value)
    return all(abs(a - b) <= tolerance for a, b in (
        (color.red(), expected.red()), (color.green(), expected.green()), (color.blue(), expected.blue())))


def test_accent_line_draws_theme_colours_and_flows(app):
    theme = BUILTIN_THEMES["pride-trans"]
    line = AccentLine(None, 4)
    line.resize(500, 4)
    line.set_theme(theme)
    first = _pixel(line, 0)
    assert _close(first, theme.stripes[0])             # linker Rand = erste Streifenfarbe
    line.set_flow(True)
    line._phase = 0.5
    moved = _pixel(line, 0)
    assert not _close(moved, theme.stripes[0])         # Verlauf ist verschoben
    line.set_flow(False)
    assert _close(_pixel(line, 0), theme.stripes[0])   # ohne Bewegung wieder Grundzustand
    line.pause(True)
    line.pause(False)


def test_single_colour_theme_does_not_crash(app):
    line = AccentLine(None, 4)
    line.resize(200, 4)
    line.set_theme(BUILTIN_THEMES["dunkel"])           # keine Streifen
    line.set_flow(True)
    assert _close(_pixel(line, 100), BUILTIN_THEMES["dunkel"].accent)


def test_accent_line_timer_follows_visibility_and_pause(app):
    line = AccentLine(None, 4)
    line.resize(300, 4)
    line.set_theme(BUILTIN_THEMES["pride-trans"])
    line.set_flow(True)
    assert not line._timer.isActive()          # unsichtbar: kein Timer, kein Stromverbrauch
    line.show()
    assert line._timer.isActive()
    line.pause(True)                           # Fenster im Hintergrund
    assert not line._timer.isActive()
    line.set_flow(True)
    assert not line._timer.isActive()          # Pause bleibt bestehen
    line.pause(False)
    assert line._timer.isActive()
    line.set_flow(False)
    assert not line._timer.isActive()
    line.hide()
