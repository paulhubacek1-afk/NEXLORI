"""Tab-Leiste und Seitenstapel als getrennte Widgets.

Die Tab-Leiste (``bar``) sitzt unter der Titelleiste, der Seitenstapel (``stack``) unter der Adress-/Suchleiste.
Mit einem normalen ``QTabWidget`` wäre das nicht möglich, weil dort Leiste und Seiten untrennbar zusammenhängen –
genau deshalb lag die Suchleiste früher unter der Webseite.

``TabStrip`` bietet dieselben Methoden wie ``QTabWidget`` (``addTab``, ``widget``, ``indexOf`` …), damit der
restliche Browsercode unverändert bleiben kann. Leiste und Stapel haben immer dieselbe Reihenfolge.
"""
from __future__ import annotations

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import QStackedWidget, QTabBar, QWidget


class TabStrip(QObject):
    currentChanged = Signal(int)
    tabCloseRequested = Signal(int)

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self.bar = QTabBar()
        self.bar.setObjectName("tabBar")
        self.bar.setDocumentMode(True)
        self.bar.setMovable(True)
        self.bar.setTabsClosable(True)
        self.bar.setExpanding(False)
        self.bar.setDrawBase(False)
        self.bar.setUsesScrollButtons(True)
        self.bar.setElideMode(Qt.TextElideMode.ElideRight)
        self.stack = QStackedWidget()
        self.stack.setObjectName("pageStack")
        self.bar.currentChanged.connect(self._bar_current_changed)
        self.bar.tabCloseRequested.connect(self.tabCloseRequested)
        self.bar.tabMoved.connect(self._bar_tab_moved)

    # ------------------------------------------------------------------ Synchronisation
    def _bar_current_changed(self, index: int) -> None:
        if 0 <= index < self.stack.count():
            self.stack.setCurrentIndex(index)
            self.currentChanged.emit(index)

    def _bar_tab_moved(self, source: int, target: int) -> None:
        widget = self.stack.widget(source)
        if widget is None:
            return
        self.stack.removeWidget(widget)
        self.stack.insertWidget(target, widget)
        self.stack.setCurrentIndex(self.bar.currentIndex())

    # ------------------------------------------------------------------ QTabWidget-kompatible API
    def addTab(self, widget: QWidget, title: str) -> int:  # noqa: N802
        index = self.bar.count()
        self.stack.insertWidget(index, widget)  # zuerst der Stapel, damit currentChanged einen Index findet
        return self.bar.addTab(title)

    def removeTab(self, index: int) -> None:  # noqa: N802
        widget = self.stack.widget(index)
        if widget is not None:
            self.stack.removeWidget(widget)
        self.bar.removeTab(index)

    def widget(self, index: int) -> QWidget | None:
        return self.stack.widget(index)

    def indexOf(self, widget: QWidget) -> int:  # noqa: N802
        return self.stack.indexOf(widget)

    def count(self) -> int:
        return self.bar.count()

    def currentIndex(self) -> int:  # noqa: N802
        return self.bar.currentIndex()

    def setCurrentIndex(self, index: int) -> None:  # noqa: N802
        self.bar.setCurrentIndex(index)

    def currentWidget(self) -> QWidget | None:  # noqa: N802
        return self.stack.widget(self.bar.currentIndex()) if self.bar.currentIndex() >= 0 else None

    def setTabText(self, index: int, text: str) -> None:  # noqa: N802
        self.bar.setTabText(index, text)

    def tabText(self, index: int) -> str:  # noqa: N802
        return self.bar.tabText(index)

    def setTabToolTip(self, index: int, text: str) -> None:  # noqa: N802
        self.bar.setTabToolTip(index, text)
