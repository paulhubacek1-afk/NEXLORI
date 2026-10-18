"""Titelleiste in den Farben des aktiven Themes.

Zwei Wege, damit die Leiste der Nexlori.exe zum Theme passt:

1. **Eigene Titelleiste** (Standard): Das Fenster ist rahmenlos, ``TitleBar`` zeichnet Symbol, Titel und die Knöpfe
   Minimieren/Maximieren/Schließen in Theme-Farben. Verschieben, Größe ändern und Andocken am Bildschirmrand laufen
   über die Funktionen des Betriebssystems (``startSystemMove`` / ``startSystemResize``).
2. **Windows-Standardleiste** (Einstellung „Eigene Titelleiste“ aus): Die normale Leiste wird über die DWM-Schnittstelle
   eingefärbt (Windows 11 vollständig, Windows 10 nur hell/dunkel).

``apply_native_titlebar_colors`` wird zusätzlich für Dialoge verwendet, damit auch Einstellungen & Co. passen.
"""
from __future__ import annotations

import sys

from PySide6.QtCore import QEvent, QObject, QRect, Qt
from PySide6.QtGui import QColor, QCursor, QIcon, QPainter, QPen
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QToolButton, QVBoxLayout, QWidget

from .core.themes import Theme, hex_to_rgb, relative_luminance

TITLEBAR_HEIGHT = 42
RESIZE_MARGIN = 5


def colorref(value: str) -> int:
    """#RRGGBB -> Windows-COLORREF (0x00BBGGRR)."""
    r, g, b = hex_to_rgb(value)
    return r | (g << 8) | (b << 16)


def apply_native_titlebar_colors(widget: QWidget, theme: Theme) -> bool:
    """Färbt die Windows-Titelleiste eines Fensters/Dialogs ein. Auf anderen Systemen: keine Wirkung."""
    if sys.platform != "win32":
        return False
    try:
        import ctypes
        from ctypes import wintypes

        hwnd = wintypes.HWND(int(widget.winId()))
        dwm = ctypes.windll.dwmapi

        def set_attribute(attribute: int, value: int) -> int:
            data = ctypes.c_int(value)
            return dwm.DwmSetWindowAttribute(hwnd, attribute, ctypes.byref(data), ctypes.sizeof(data))

        dark = relative_luminance(theme.bg) < 0.5
        set_attribute(20, 1 if dark else 0)          # DWMWA_USE_IMMERSIVE_DARK_MODE (Windows 10 1903+)
        set_attribute(35, colorref(theme.surface))   # DWMWA_CAPTION_COLOR (Windows 11)
        set_attribute(36, colorref(theme.fg))        # DWMWA_TEXT_COLOR (Windows 11)
        set_attribute(34, colorref(theme.accent))    # DWMWA_BORDER_COLOR (Windows 11)
        return True
    except Exception:  # noqa: BLE001 - rein kosmetisch, darf nie den Start verhindern
        return False


class DialogThemer(QObject):
    """Färbt die Titelleiste aller Dialoge ein, sobald sie erscheinen (Windows)."""

    def __init__(self, get_theme, parent: QObject | None = None):
        super().__init__(parent)
        self._get_theme = get_theme

    def eventFilter(self, obj, event) -> bool:  # noqa: N802
        if event.type() == QEvent.Type.Show and isinstance(obj, QDialog) and obj.isWindow():
            apply_native_titlebar_colors(obj, self._get_theme())
        return False


class TitleBar(QWidget):
    """Symbol, Titel und Fensterknöpfe. Ein Klick-und-Ziehen verschiebt das Fenster."""

    def __init__(self, window: QWidget):
        super().__init__(window)
        self._window = window
        self.setObjectName("titleBar")
        self.setFixedHeight(TITLEBAR_HEIGHT)
        row = QHBoxLayout(self)
        row.setContentsMargins(12, 0, 0, 0)
        row.setSpacing(10)

        self.icon_label = QLabel(self)
        self.icon_label.setFixedSize(20, 20)
        self.icon_label.setScaledContents(True)
        self.icon_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        row.addWidget(self.icon_label)

        self.title_label = QLabel("Nexlori", self)
        self.title_label.setObjectName("titleText")
        self.title_label.setFixedWidth(82)
        self.title_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        row.addWidget(self.title_label)

        self.tabs_host = QWidget(self)
        self.tabs_host.setObjectName("titleTabsHost")
        self.tabs_host.setMinimumWidth(0)
        self.tabs_layout = QHBoxLayout(self.tabs_host)
        self.tabs_layout.setContentsMargins(0, 0, 2, 0)
        self.tabs_layout.setSpacing(3)
        row.addWidget(self.tabs_host, 1)

        self.min_button = self._button("–", "Minimieren", self._minimize, "titleButton")
        self.max_button = self._button("☐", "Maximieren", self._toggle_maximize, "titleButton")
        self.close_button = self._button("✕", "Schließen", window.close, "titleCloseButton")
        for button in (self.min_button, self.max_button, self.close_button):
            row.addWidget(button)

    def set_tab_widgets(self, new_tab_button: QWidget, tab_bar: QWidget) -> None:
        """Put the new-tab control and closable tabs directly in the window's top title bar."""
        for widget in (new_tab_button, tab_bar):
            widget.setParent(self.tabs_host)
            self.tabs_layout.addWidget(widget)
        self.tabs_host.setVisible(True)

    def _button(self, text: str, tip: str, callback, name: str) -> QToolButton:
        button = QToolButton(self)
        button.setObjectName(name)
        button.setText(text)
        button.setToolTip(tip)
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        button.setCursor(Qt.CursorShape.ArrowCursor)
        button.setFixedSize(46, TITLEBAR_HEIGHT)
        button.clicked.connect(callback)
        return button

    # ---------------------------------------------------------------- Zustand
    def set_title(self, text: str) -> None:
        metrics = self.title_label.fontMetrics()
        self.title_label.setText(metrics.elidedText(text, Qt.TextElideMode.ElideRight, max(40, self.title_label.width())))
        self.title_label.setToolTip(text)

    def set_icon(self, icon: QIcon) -> None:
        self.icon_label.setPixmap(icon.pixmap(40, 40))

    def set_maximized(self, maximized: bool) -> None:
        self.max_button.setText("❐" if maximized else "☐")
        self.max_button.setToolTip("Verkleinern" if maximized else "Maximieren")

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self.set_title(self.title_label.toolTip() or self.title_label.text())

    # ---------------------------------------------------------------- Aktionen
    def _minimize(self) -> None:
        self._window.showMinimized()

    def _toggle_maximize(self) -> None:
        if self._window.isMaximized():
            self._window.showNormal()
        else:
            self._window.showMaximized()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            handle = self._window.windowHandle()
            if handle is not None and not self._window.isFullScreen():
                handle.startSystemMove()
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._toggle_maximize()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)


class ResizeFrame(QWidget):
    """Zentrales Widget mit schmalem Rand, über den ein rahmenloses Fenster in der Größe verändert wird."""

    def __init__(self, window: QWidget, content: QWidget):
        super().__init__(window)
        self._window = window
        self._resizable = True
        self._fill = QColor("#222222")
        self._border = QColor("#888888")
        self.setMouseTracking(True)
        self._layout = QVBoxLayout(self)
        self._layout.setSpacing(0)
        self._layout.addWidget(content)
        self.set_resizable(True)

    def set_colors(self, fill: str, border: str) -> None:
        self._fill, self._border = QColor(fill), QColor(border)
        self.update()

    def set_resizable(self, enabled: bool) -> None:
        self._resizable = bool(enabled)
        margin = RESIZE_MARGIN if enabled else 0
        self._layout.setContentsMargins(margin, margin, margin, margin)
        if not enabled:
            self.unsetCursor()
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.fillRect(self.rect(), self._fill)
        if self._resizable:
            painter.setPen(QPen(self._border, 1))
            painter.drawRect(QRect(0, 0, self.width() - 1, self.height() - 1))
        painter.end()

    def _edges_at(self, x: int, y: int) -> Qt.Edge:
        edges = Qt.Edge(0)
        if not self._resizable:
            return edges
        # Etwas großzügigere Ecken, damit sie sich leicht treffen lassen
        corner = RESIZE_MARGIN * 3
        if x < RESIZE_MARGIN or (x < corner and (y < RESIZE_MARGIN or y >= self.height() - RESIZE_MARGIN)):
            edges |= Qt.Edge.LeftEdge
        if x >= self.width() - RESIZE_MARGIN or (
            x >= self.width() - corner and (y < RESIZE_MARGIN or y >= self.height() - RESIZE_MARGIN)
        ):
            edges |= Qt.Edge.RightEdge
        if y < RESIZE_MARGIN or (y < corner and (x < RESIZE_MARGIN or x >= self.width() - RESIZE_MARGIN)):
            edges |= Qt.Edge.TopEdge
        if y >= self.height() - RESIZE_MARGIN or (
            y >= self.height() - corner and (x < RESIZE_MARGIN or x >= self.width() - RESIZE_MARGIN)
        ):
            edges |= Qt.Edge.BottomEdge
        return edges

    @staticmethod
    def cursor_for(edges: Qt.Edge) -> Qt.CursorShape | None:
        horizontal = bool(edges & (Qt.Edge.LeftEdge | Qt.Edge.RightEdge))
        vertical = bool(edges & (Qt.Edge.TopEdge | Qt.Edge.BottomEdge))
        if horizontal and vertical:
            diagonal_main = (edges & Qt.Edge.LeftEdge and edges & Qt.Edge.TopEdge) or (
                edges & Qt.Edge.RightEdge and edges & Qt.Edge.BottomEdge
            )
            return Qt.CursorShape.SizeFDiagCursor if diagonal_main else Qt.CursorShape.SizeBDiagCursor
        if horizontal:
            return Qt.CursorShape.SizeHorCursor
        if vertical:
            return Qt.CursorShape.SizeVerCursor
        return None

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        pos = event.position().toPoint()
        shape = self.cursor_for(self._edges_at(pos.x(), pos.y()))
        if shape is None:
            self.unsetCursor()
        else:
            self.setCursor(QCursor(shape))
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position().toPoint()
            edges = self._edges_at(pos.x(), pos.y())
            handle = self._window.windowHandle()
            if edges and handle is not None:
                handle.startSystemResize(edges)
                event.accept()
                return
        super().mousePressEvent(event)
