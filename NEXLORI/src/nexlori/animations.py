"""Sanfte Animationen für Nexlori – alle abschaltbar (Einstellungen → Animationen).

Stufen:
- ``full``: fließender Farbverlauf in der Akzentlinie, weiche Theme-Wechsel, Fenster-Einblendung, Lade-Animation
- ``reduced``: nur kurze Übergänge, keine Dauerbewegung (schont Akku und ist ruhiger)
- ``off``: keine Animationen
"""
from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QRect, Qt, QTimer
from PySide6.QtGui import QColor, QLinearGradient, QPainter
from PySide6.QtWidgets import QGraphicsOpacityEffect, QLabel, QProgressBar, QWidget

from .core.themes import Theme


class Motion:
    """Übersetzt die Einstellung in konkrete Dauern."""

    def __init__(self, mode: str = "full"):
        self.mode = mode if mode in ("full", "reduced", "off") else "full"

    @property
    def enabled(self) -> bool:
        return self.mode != "off"

    @property
    def continuous(self) -> bool:
        return self.mode == "full"

    def ms(self, base: int) -> int:
        if self.mode == "off":
            return 0
        return base if self.mode == "full" else max(1, base // 2)


class AccentLine(QWidget):
    """Farbleiste unter der Titelleiste: zeigt die Theme-Streifen und lässt sie langsam fließen."""

    PERIOD_MS = 14000
    TICK_MS = 40

    def __init__(self, parent: QWidget | None = None, height: int = 4):
        super().__init__(parent)
        self.setFixedHeight(height)
        self._colors: tuple[str, ...] = ("#888888",)
        self._phase = 0.0
        self._flow = False
        self._paused = False
        self._timer = QTimer(self)
        self._timer.setInterval(self.TICK_MS)
        self._timer.timeout.connect(self._tick)

    def set_theme(self, theme: Theme) -> None:
        colors = tuple(theme.stripes) or (theme.accent,)
        self._colors = colors if len(colors) > 1 else (colors[0], colors[0])
        self.update()

    def set_flow(self, enabled: bool) -> None:
        """Dauerbewegung ein-/ausschalten (nur sinnvoll, wenn mehrere Farben vorhanden sind)."""
        self._flow = bool(enabled)
        self._sync_timer()
        self.update()

    def _sync_timer(self) -> None:
        should_run = self._flow and not self._paused and self.isVisible() and len(set(self._colors)) > 1
        if should_run and not self._timer.isActive():
            self._timer.start()
        elif not should_run and self._timer.isActive():
            self._timer.stop()

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self._sync_timer()

    def hideEvent(self, event) -> None:  # noqa: N802
        super().hideEvent(event)
        self._sync_timer()

    def pause(self, paused: bool) -> None:
        """Pausiert die Bewegung, solange das Fenster im Hintergrund ist (spart Akku)."""
        self._paused = bool(paused)
        self._sync_timer()

    def _tick(self) -> None:
        self._phase = (self._phase + self.TICK_MS / self.PERIOD_MS) % 1.0
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802
        width, height = self.width(), self.height()
        if width <= 0:
            return
        painter = QPainter(self)
        colors = self._colors
        loop = list(colors) + [colors[0]]  # nahtloser Übergang vom Ende zum Anfang
        offset = self._phase * width if self._flow else 0.0
        for start in (-offset, width - offset):
            gradient = QLinearGradient(start, 0, start + width, 0)
            for index, color in enumerate(loop):
                gradient.setColorAt(index / (len(loop) - 1), QColor(color))
            painter.fillRect(QRect(int(start), 0, width + 1, height), gradient)
        painter.end()


def crossfade(window: QWidget, region: QRect, apply_change, motion: Motion) -> None:
    """Führt ``apply_change`` aus und blendet den alten Zustand von ``region`` weich aus.

    Nur die Bedienleisten werden überblendet – der Webseiten-Bereich enthält GPU-Inhalt und wird nicht abfotografiert.
    """
    duration = motion.ms(260)
    if duration <= 0 or region.height() <= 0 or not window.isVisible():
        apply_change()
        return
    overlay = QLabel(window)
    overlay.setPixmap(window.grab(region))
    overlay.setGeometry(region)
    overlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    overlay.show()
    overlay.raise_()
    apply_change()
    effect = QGraphicsOpacityEffect(overlay)
    overlay.setGraphicsEffect(effect)
    animation = QPropertyAnimation(effect, b"opacity", overlay)
    animation.setDuration(duration)
    animation.setStartValue(1.0)
    animation.setEndValue(0.0)
    animation.setEasingCurve(QEasingCurve.Type.OutCubic)
    animation.finished.connect(overlay.deleteLater)
    animation.start()
    overlay._animation = animation  # Referenz halten, bis die Animation fertig ist


def cascade_in(widgets: list[QWidget], motion: Motion) -> None:
    """Blendet Titelleiste, Tabs und Suchleiste nacheinander ein.

    Bewusst nur für die Bedienleisten: ein Deckkraft-Effekt auf dem Fenster oder auf der Webseite kann bei
    Chromium zu Flackern führen. Der Effekt wird nach der Animation wieder entfernt.
    """
    duration = motion.ms(320)
    if duration <= 0:
        return
    for index, widget in enumerate(w for w in widgets if w is not None):
        effect = QGraphicsOpacityEffect(widget)
        effect.setOpacity(0.0)
        widget.setGraphicsEffect(effect)
        animation = QPropertyAnimation(effect, b"opacity", widget)
        animation.setDuration(duration)
        animation.setStartValue(0.0)
        animation.setEndValue(1.0)
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        animation.finished.connect(lambda w=widget: w.setGraphicsEffect(None))
        widget._cascade_animation = animation
        QTimer.singleShot(index * motion.ms(90), animation.start)


def animate_progress(bar: QProgressBar, value: int, motion: Motion) -> None:
    """Lässt den Ladebalken gleiten, statt zu springen."""
    duration = motion.ms(220)
    previous = getattr(bar, "_value_animation", None)
    if previous is not None:
        previous.stop()
    if duration <= 0 or value <= bar.value():
        bar.setValue(value)
        return
    animation = QPropertyAnimation(bar, b"value", bar)
    animation.setDuration(duration)
    animation.setStartValue(bar.value())
    animation.setEndValue(value)
    animation.setEasingCurve(QEasingCurve.Type.OutCubic)
    animation.start()
    bar._value_animation = animation
