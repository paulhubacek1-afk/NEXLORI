"""Fenster-Oberfläche (Tkinter): Tabs, Adressleiste, Seitenansicht, Menü.

Die Seite wird NICHT von Tk gezeichnet, sondern vom eigenen Renderer (engine/) in ein Bild; Tk zeigt nur
den sichtbaren Ausschnitt an. Laden und Layout laufen in Hintergrund-Threads, damit das Fenster nie einfriert.
"""
from __future__ import annotations

import queue
import sys
import threading
import time
import tkinter as tk
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from tkinter import font as tkfont
from tkinter import messagebox

from PIL import ImageTk

from . import __version__
from .browser import BrowserSession, Page, error_page, load_page, resolve_link
from .core.gaming import EXAMPLE_GAME_PROCESSES, GamingDetector
from .core.modes import Mode
from .core.settings import Settings, default_settings_path
from .core.themes import BUILTIN_THEMES
from .engine import paint
from .engine.fonts import default_metrics
from .engine.layout import Layout, Text
from .icon import make_icon

MODE_LABELS = {
    Mode.NORMAL: "Normal",
    Mode.ECO: "Ressourcenschonend",
    Mode.BATTERY: "Akku",
    Mode.GAMING: "Gaming",
}
ZOOM_STEP = 0.1


def _hex(rgb: tuple[int, int, int]) -> str:
    return "#%02x%02x%02x" % rgb


class _Pool:
    """Kleiner Thread-Pool aus Daemon-Threads (ein hängender Abruf darf das Beenden nie blockieren)."""

    def __init__(self, workers: int = 4):
        self._q: queue.Queue = queue.Queue()
        for i in range(workers):
            threading.Thread(target=self._run, daemon=True, name=f"nexlori-worker-{i}").start()

    def submit(self, fn, *args) -> None:
        self._q.put((fn, args))

    def _run(self) -> None:
        while True:
            fn, args = self._q.get()
            try:
                fn(*args)
            except Exception:  # noqa: BLE001 - Jobs melden Fehler selbst über die Ergebnis-Queue
                pass


@dataclass
class TabState:
    id: int
    page: Page | None = None
    layout: Layout | None = None
    layout_key: tuple | None = None
    links: list = field(default_factory=list)
    scroll: float = 0.0
    load_gen: int = 0
    layout_gen: int = 0
    loading: bool = False
    title: str = "Neuer Tab"
    widgets: tuple | None = None  # (frame, underline, title_label, close_label)


class NexloriApp:
    def __init__(self, root: tk.Tk, settings: Settings, settings_path: Path | None = None, start_url: str = "about:start"):
        self.root = root
        self.settings = settings
        self.settings_path = settings_path
        self.session = BrowserSession(settings)
        self.states: dict[int, TabState] = {}
        self.results: queue.Queue = queue.Queue()
        self.pool = _Pool(4)
        self.metrics = default_metrics()
        self.theme = BUILTIN_THEMES.get(settings.theme, BUILTIN_THEMES["dunkel"])
        self._photo = None
        self._last_image = None  # zuletzt gezeichneter Ausschnitt (für Tests/Diagnose)
        self._redraw_pending = False
        self._relayout_job = None
        self._poll_busy = False
        self._status_msg = ""
        self._closing = False

        dpi_scale = root.winfo_fpixels("1i") / 96.0
        self.base_scale = min(3.0, max(1.0, round(dpi_scale * 4) / 4))

        self.detector = GamingDetector(
            game_names=set(EXAMPLE_GAME_PROCESSES) | {g.lower() for g in settings.custom_games},
            enabled=settings.gaming_detection,
        )
        # Der Detektor läuft in einem Hintergrund-Thread: nur Ereignis in die Queue legen, Verarbeitung im UI-Thread.
        self.detector.subscribe(lambda active: self.results.put(("gaming", active)))
        self.session.modes.subscribe(lambda _mode: self._update_status())

        self._build_ui()
        self._apply_theme()
        self.root.after(40, self._poll)
        self.root.after(15_000, self._tick_sleep)
        self.root.after(5_000, self._tick_gaming)
        tab = self.new_tab()
        self.navigate(tab, start_url)

    # ----------------------------------------------------------------------------- Aufbau
    @property
    def zoom(self) -> float:
        return round(self.base_scale * self.settings.page_zoom, 3)

    @property
    def active_id(self) -> int | None:
        return self.session.tabs.active_id

    @property
    def active(self) -> TabState | None:
        return self.states.get(self.active_id) if self.active_id is not None else None

    def _build_ui(self) -> None:
        r = self.root
        r.title("Nexlori")
        r.geometry("1100x760")
        r.minsize(520, 360)
        try:
            self._icon = ImageTk.PhotoImage(make_icon(64))
            r.iconphoto(True, self._icon)
        except Exception:  # noqa: BLE001 - das Icon ist nur Kosmetik
            pass
        base = tkfont.nametofont("TkDefaultFont")
        self.font_normal = base.copy()
        self.font_italic = base.copy()
        self.font_italic.configure(slant="italic")
        self.font_big = base.copy()
        self.font_big.configure(size=max(base.cget("size"), 10) + 3)

        self.stripe = tk.Canvas(r, height=4, highlightthickness=0, bd=0)
        self.stripe.pack(fill="x")
        self.stripe.bind("<Configure>", lambda _e: self._draw_stripe())

        self.tabbar = tk.Frame(r)
        self.tabbar.pack(fill="x")
        self.tab_area = tk.Frame(self.tabbar)
        self.tab_area.pack(side="left")
        self.btn_new = self._button(self.tabbar, "+", self.cmd_new_tab, big=True)
        self.btn_new.pack(side="left", padx=4)

        self.toolbar = tk.Frame(r)
        self.toolbar.pack(fill="x", padx=6, pady=6)
        self.btn_back = self._button(self.toolbar, "←", self.cmd_back, big=True)
        self.btn_fwd = self._button(self.toolbar, "→", self.cmd_forward, big=True)
        self.btn_reload = self._button(self.toolbar, "↻", self.cmd_reload, big=True)
        self.btn_menu = self._button(self.toolbar, "☰", self._open_menu, big=True)
        for b in (self.btn_back, self.btn_fwd, self.btn_reload):
            b.pack(side="left", padx=2)
        self.btn_menu.pack(side="right", padx=2)
        self.var_url = tk.StringVar()
        self.entry = tk.Entry(self.toolbar, textvariable=self.var_url, relief="flat", highlightthickness=2, bd=4)
        self.entry.pack(side="left", fill="x", expand=True, padx=8)
        self.entry.bind("<Return>", self._on_enter)
        self.entry.bind("<FocusIn>", lambda _e: self.entry.after(10, lambda: self.entry.select_range(0, "end")))

        self.status = tk.Frame(r)
        self.status.pack(side="bottom", fill="x")
        self.var_status = tk.StringVar()
        self.var_mode = tk.StringVar()
        self.lbl_status = tk.Label(self.status, textvariable=self.var_status, anchor="w", padx=8)
        self.lbl_status.pack(side="left", fill="x", expand=True)
        self.lbl_mode = tk.Label(self.status, textvariable=self.var_mode, anchor="e", padx=8)
        self.lbl_mode.pack(side="right")

        self.view = tk.Frame(r)
        self.view.pack(fill="both", expand=True)
        self.scrollbar = tk.Scrollbar(self.view, orient="vertical", command=self._on_scrollbar)
        self.scrollbar.pack(side="right", fill="y")
        self.canvas = tk.Canvas(self.view, highlightthickness=0, bd=0, takefocus=1)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.canvas.bind("<Configure>", self._on_resize)
        self.canvas.bind("<Button-1>", self._on_click)
        self.canvas.bind("<Button-2>", lambda e: self._on_click(e, force_new_tab=True))
        self.canvas.bind("<Motion>", self._on_motion)
        self.canvas.bind("<Leave>", lambda _e: self._set_status(""))
        self.canvas.bind("<MouseWheel>", self._on_wheel)
        self.canvas.bind("<Button-4>", lambda e: self._on_wheel(e, linux=+1))
        self.canvas.bind("<Button-5>", lambda e: self._on_wheel(e, linux=-1))
        for key, fn in (
            ("<Up>", lambda: self._scroll_by(-60 * self.zoom)),
            ("<Down>", lambda: self._scroll_by(60 * self.zoom)),
            ("<Prior>", lambda: self._scroll_by(-self.canvas.winfo_height() * 0.9)),
            ("<Next>", lambda: self._scroll_by(self.canvas.winfo_height() * 0.9)),
            ("<space>", lambda: self._scroll_by(self.canvas.winfo_height() * 0.9)),
            ("<Home>", lambda: self._scroll_to(0)),
            ("<End>", lambda: self._scroll_to(1e12)),
        ):
            self.canvas.bind(key, lambda _e, f=fn: f())

        for seq, fn in (
            ("<Control-t>", self.cmd_new_tab),
            ("<Control-w>", self.cmd_close_tab),
            ("<Control-l>", self.cmd_focus_address),
            ("<F5>", self.cmd_reload),
            ("<Control-r>", self.cmd_reload),
            ("<Alt-Left>", self.cmd_back),
            ("<Alt-Right>", self.cmd_forward),
            ("<Control-plus>", lambda: self.change_zoom(+ZOOM_STEP)),
            ("<Control-equal>", lambda: self.change_zoom(+ZOOM_STEP)),
            ("<Control-KP_Add>", lambda: self.change_zoom(+ZOOM_STEP)),
            ("<Control-minus>", lambda: self.change_zoom(-ZOOM_STEP)),
            ("<Control-KP_Subtract>", lambda: self.change_zoom(-ZOOM_STEP)),
            ("<Control-0>", lambda: self.change_zoom(None)),
            ("<Control-Tab>", lambda: self.cycle_tab(+1)),
            ("<Control-Shift-Tab>", lambda: self.cycle_tab(-1)),
        ):
            self.root.bind_all(seq, lambda _e, f=fn: (f(), "break")[1])
        self.root.protocol("WM_DELETE_WINDOW", self.quit)
        self.root.report_callback_exception = self._on_callback_error

        self.menu = tk.Menu(self.root, tearoff=0)
        self.var_theme = tk.StringVar(value=self.settings.theme)
        self.var_mode_choice = tk.StringVar(value=self.settings.mode)
        self.var_gaming = tk.BooleanVar(value=self.settings.gaming_detection)
        self.var_autoswitch = tk.BooleanVar(value=self.settings.gaming_auto_switch)
        m = self.menu
        m.add_command(label="Neuer Tab\tStrg+T", command=self.cmd_new_tab)
        m.add_command(label="Tab schließen\tStrg+W", command=self.cmd_close_tab)
        m.add_separator()
        themes = tk.Menu(m, tearoff=0)
        for name, theme in BUILTIN_THEMES.items():
            themes.add_radiobutton(label=theme.label, variable=self.var_theme, value=name, command=lambda n=name: self.set_theme(n))
        m.add_cascade(label="Design", menu=themes)
        modes = tk.Menu(m, tearoff=0)
        for mode in (Mode.NORMAL, Mode.ECO, Mode.BATTERY):
            modes.add_radiobutton(label=MODE_LABELS[mode], variable=self.var_mode_choice, value=mode.value, command=lambda md=mode: self.set_mode(md))
        m.add_cascade(label="Modus", menu=modes)
        zoom = tk.Menu(m, tearoff=0)
        zoom.add_command(label="Vergrößern\tStrg++", command=lambda: self.change_zoom(+ZOOM_STEP))
        zoom.add_command(label="Verkleinern\tStrg+-", command=lambda: self.change_zoom(-ZOOM_STEP))
        zoom.add_command(label="Zurücksetzen\tStrg+0", command=lambda: self.change_zoom(None))
        m.add_cascade(label="Zoom", menu=zoom)
        m.add_separator()
        m.add_checkbutton(label="Gaming-Erkennung (freiwillig, nur lokal)", variable=self.var_gaming, command=self.toggle_gaming)
        m.add_checkbutton(label="Bei Spielstart automatisch Gaming-Modus", variable=self.var_autoswitch, command=self.toggle_autoswitch)
        m.add_separator()
        m.add_command(label="Startseite", command=lambda: self.navigate(self.active_id, "about:start"))
        m.add_command(label="Interne Testseite", command=lambda: self.navigate(self.active_id, "about:test"))
        m.add_separator()
        m.add_command(label="Beenden", command=self.quit)

    def _button(self, parent, text, command, big: bool = False) -> tk.Label:
        lbl = tk.Label(parent, text=text, padx=9, pady=3, cursor="hand2", font=self.font_big if big else self.font_normal)
        lbl.bind("<Button-1>", lambda _e: command())
        lbl.bind("<Enter>", lambda _e: lbl.configure(bg=self.theme.surface) if lbl.cget("bg") == self.theme.bg else None)
        lbl.bind("<Leave>", lambda _e: lbl.configure(bg=self._button_bg(lbl)))
        lbl._nx_parent = parent  # type: ignore[attr-defined]
        return lbl

    def _button_bg(self, lbl: tk.Label) -> str:
        return self.theme.surface if lbl._nx_parent is self.tabbar else self.theme.bg  # type: ignore[attr-defined]

    # ----------------------------------------------------------------------------- Theme
    def _apply_theme(self) -> None:
        t = self.theme
        self.root.configure(bg=t.bg)
        self.stripe.configure(bg=t.bg)
        self._draw_stripe()
        for w in (self.tabbar, self.tab_area):
            w.configure(bg=t.surface)
        self.toolbar.configure(bg=t.bg)
        self.view.configure(bg=t.bg)
        for b in (self.btn_new, self.btn_back, self.btn_fwd, self.btn_reload, self.btn_menu):
            b.configure(bg=self._button_bg(b), fg=t.fg)
        self.entry.configure(
            bg=t.surface, fg=t.fg, insertbackground=t.fg, highlightbackground=t.surface, highlightcolor=t.accent,
            selectbackground=t.accent, selectforeground=t.bg, disabledbackground=t.surface,
        )
        self.status.configure(bg=t.surface)
        for lbl in (self.lbl_status, self.lbl_mode):
            lbl.configure(bg=t.surface, fg=t.fg)
        for st in self.states.values():
            self._style_tab(st)
        self._update_nav()

    def _draw_stripe(self) -> None:
        self.stripe.delete("all")
        colors = self.theme.stripes or (self.theme.accent,)
        width = max(1, self.stripe.winfo_width())
        step = width / len(colors)
        for i, color in enumerate(colors):
            self.stripe.create_rectangle(i * step, 0, (i + 1) * step + 1, 6, fill=color, outline=color)

    def set_theme(self, name: str) -> None:
        self.theme = BUILTIN_THEMES[name]
        self.settings.theme = name
        self._apply_theme()
        self._save_settings()
        self._schedule_redraw()

    # ----------------------------------------------------------------------------- Tabs
    def new_tab(self, url: str | None = None, activate: bool = True) -> int:
        tab_id = self.session.open_tab(time.monotonic(), activate=activate)
        st = TabState(tab_id)
        self.states[tab_id] = st
        self._make_tab_widget(st)
        if activate:
            self._show_active()
        if url:
            self.navigate(tab_id, url)
        return tab_id

    def _make_tab_widget(self, st: TabState) -> None:
        frame = tk.Frame(self.tab_area)
        under = tk.Frame(frame, height=2)
        under.pack(side="bottom", fill="x")
        title = tk.Label(frame, text=st.title, width=22, anchor="w", padx=8, pady=5, cursor="hand2")
        title.pack(side="left")
        close = tk.Label(frame, text="×", padx=6, cursor="hand2")
        close.pack(side="left")
        frame.pack(side="left", padx=(0, 2))
        title.bind("<Button-1>", lambda _e, i=st.id: self.select_tab(i))
        title.bind("<Button-2>", lambda _e, i=st.id: self.close_tab(i))
        close.bind("<Button-1>", lambda _e, i=st.id: self.close_tab(i))
        st.widgets = (frame, under, title, close)
        self._style_tab(st)

    def _style_tab(self, st: TabState) -> None:
        if st.widgets is None:
            return
        t = self.theme
        frame, under, title, close = st.widgets
        is_active = st.id == self.active_id
        bg = t.bg if is_active else t.surface
        sleeping = st.id in self.session.tabs.tabs and self.session.tabs.tabs[st.id].suspended
        for w in (frame, title, close):
            w.configure(bg=bg)
        title.configure(fg=t.fg, font=self.font_italic if sleeping else self.font_normal)
        close.configure(fg=t.fg)
        under.configure(bg=t.accent if is_active else t.surface)
        text = ("Lädt … " if st.loading and st.title == "Neuer Tab" else st.title) or "Ohne Titel"
        title.configure(text=text if len(text) <= 24 else text[:23] + "…")

    def select_tab(self, tab_id: int) -> None:
        if tab_id not in self.states:
            return
        self.session.tabs.activate(tab_id, time.monotonic())
        st = self.states[tab_id]
        if st.page is not None and st.page.document is None and not st.loading:
            self.navigate(tab_id, st.page.url, push=False)  # Ruhezustand beenden: Seite neu laden
        self._show_active()

    def cycle_tab(self, step: int) -> None:
        ids = list(self.states)
        if len(ids) > 1 and self.active_id in ids:
            self.select_tab(ids[(ids.index(self.active_id) + step) % len(ids)])

    def close_tab(self, tab_id: int | None) -> None:
        if tab_id is None or tab_id not in self.states:
            return
        ids = list(self.states)
        idx = ids.index(tab_id)
        was_active = tab_id == self.active_id
        st = self.states.pop(tab_id)
        if st.widgets:
            st.widgets[0].destroy()
        self.session.close_tab(tab_id)
        if not self.states:
            self.quit()
            return
        if was_active:
            remaining = list(self.states)
            self.select_tab(remaining[min(idx, len(remaining) - 1)])
        else:
            self._update_status()

    def _show_active(self, *, from_load: bool = False) -> None:
        for st in self.states.values():
            self._style_tab(st)
        st = self.active
        if st is None:
            return
        page = st.page
        typing = from_load and self.root.focus_get() is self.entry  # laufende Eingabe nicht überschreiben
        if not typing:
            self.var_url.set(page.url if page else "")
        self.root.title(f"{st.title} – Nexlori" if page else "Nexlori")
        self._update_nav()
        self._update_status()
        self._request_layout(st)
        self._schedule_redraw()
        if not typing and not (from_load and self.root.focus_get() is not None and self.root.focus_get() is not self.canvas):
            self.canvas.focus_set()

    # ----------------------------------------------------------------------------- Navigation
    def navigate(self, tab_id: int | None, url: str, push: bool = True) -> None:
        if tab_id is None or tab_id not in self.states:
            return
        st = self.states[tab_id]
        st.load_gen += 1
        st.loading = True
        self._style_tab(st)
        if tab_id == self.active_id:
            self._set_status(f"Lädt {url} …")
        self.pool.submit(self._load_job, tab_id, st.load_gen, url, push)

    def _load_job(self, tab_id: int, gen: int, url: str, push: bool) -> None:
        self.results.put(("load", tab_id, gen, push, load_page(url)))

    def cmd_new_tab(self) -> None:
        self.new_tab("about:start")
        self.cmd_focus_address()

    def cmd_close_tab(self) -> None:
        self.close_tab(self.active_id)

    def cmd_focus_address(self) -> None:
        self.entry.focus_set()
        self.entry.select_range(0, "end")

    def cmd_back(self) -> None:
        if self.active_id is not None and (url := self.session.go_back(self.active_id)):
            self.navigate(self.active_id, url, push=False)

    def cmd_forward(self) -> None:
        if self.active_id is not None and (url := self.session.go_forward(self.active_id)):
            self.navigate(self.active_id, url, push=False)

    def cmd_reload(self) -> None:
        st = self.active
        if st and st.page:
            self.navigate(st.id, st.page.url, push=False)

    def _on_enter(self, _event=None) -> None:
        self.navigate(self.active_id, self.session.resolve_input(self.var_url.get()))
        self.canvas.focus_set()

    # ----------------------------------------------------------------------------- Ergebnisse der Hintergrund-Threads
    def _poll(self) -> None:
        if self._closing:
            return
        try:
            while True:
                self._handle(self.results.get_nowait())
        except queue.Empty:
            pass
        self.root.after(40, self._poll)

    def _handle(self, item: tuple) -> None:
        kind = item[0]
        if kind == "load":
            _, tab_id, gen, push, page = item
            st = self.states.get(tab_id)
            if st is None or gen != st.load_gen:
                return  # Tab geschlossen oder neuere Navigation gestartet
            st.loading = False
            st.page, st.layout, st.layout_key, st.links, st.scroll = page, None, None, [], 0.0
            st.title = page.title
            self.session.tabs.tabs[tab_id].suspended = False
            self.session.commit(tab_id, page.url, push=push)
            self._style_tab(st)
            if tab_id == self.active_id:
                self._show_active(from_load=True)
                msg = page.note or (f"HTTP {page.status}" if page.status and page.status >= 400 else "")
                self._set_status(msg)
        elif kind == "layout":
            _, tab_id, gen, key, layout, exc = item
            st = self.states.get(tab_id)
            if st is None or gen != st.layout_gen:
                return
            if exc is not None:
                if st.page and not st.page.error:
                    st.page = error_page(st.page.url, f"Die Seite konnte nicht dargestellt werden ({type(exc).__name__}).")
                    st.layout = st.layout_key = None
                    self._request_layout(st)
                return
            st.layout, st.layout_key = layout, key
            st.links = [c for c in layout.commands if isinstance(c, Text) and c.href]
            if tab_id == self.active_id:
                self._schedule_redraw()
        elif kind == "gaming":
            self.session.modes.on_gaming_change(item[1])
            self._update_status()

    # ----------------------------------------------------------------------------- Layout / Zeichnen
    def _request_layout(self, st: TabState) -> None:
        if st.page is None or st.page.document is None:
            return
        width = max(200, self.canvas.winfo_width())
        key = (width, self.zoom)
        if st.layout is not None and st.layout_key == key:
            return
        st.layout_gen += 1
        self.pool.submit(self._layout_job, st.id, st.layout_gen, st.page.document, width, self.zoom, key)

    def _layout_job(self, tab_id: int, gen: int, doc, width: int, zoom: float, key: tuple) -> None:
        try:
            self.results.put(("layout", tab_id, gen, key, doc.layout(width, self.metrics, zoom), None))
        except BaseException as exc:  # noqa: BLE001 - z. B. RecursionError bei extrem tiefen Seiten
            self.results.put(("layout", tab_id, gen, key, None, exc))

    def _on_resize(self, _event=None) -> None:
        if self._relayout_job is not None:
            self.root.after_cancel(self._relayout_job)
        self._relayout_job = self.root.after(150, self._relayout)
        self._schedule_redraw()

    def _relayout(self) -> None:
        self._relayout_job = None
        if self.active:
            self._request_layout(self.active)

    def _schedule_redraw(self) -> None:
        if not self._redraw_pending:
            self._redraw_pending = True
            self.root.after_idle(self._redraw)

    def _redraw(self) -> None:
        self._redraw_pending = False
        st = self.active
        w, h = max(1, self.canvas.winfo_width()), max(1, self.canvas.winfo_height())
        self.canvas.delete("all")
        if st is None or st.layout is None or st.page is None or st.page.document is None:
            self.canvas.configure(bg=self.theme.bg)
            if st is not None and st.loading:
                self.canvas.create_text(w // 2, h // 3, text="Lädt …", fill=self.theme.fg, font=self.font_big)
            self.scrollbar.set(0, 1)
            return
        bg = st.page.document.background
        self.canvas.configure(bg=_hex(bg))
        st.scroll = min(max(0.0, st.scroll), max(0.0, st.layout.height - h))
        img = paint(st.layout, bg, top=st.scroll, height=h)
        self._last_image = img
        self._photo = ImageTk.PhotoImage(img)
        self.canvas.create_image(0, 0, anchor="nw", image=self._photo)
        total = max(st.layout.height, h)
        self.scrollbar.set(st.scroll / total, (st.scroll + h) / total)

    # ----------------------------------------------------------------------------- Scrollen, Zoom, Links
    def _scroll_to(self, y: float) -> None:
        st = self.active
        if st and st.layout:
            st.scroll = y
            self._schedule_redraw()

    def _scroll_by(self, dy: float) -> None:
        st = self.active
        if st:
            self._scroll_to(st.scroll + dy)

    def _on_scrollbar(self, *args) -> None:
        st = self.active
        if not st or not st.layout:
            return
        h = max(1, self.canvas.winfo_height())
        total = max(st.layout.height, h)
        if args[0] == "moveto":
            self._scroll_to(float(args[1]) * total)
        elif args[0] == "scroll":
            amount = int(args[1])
            self._scroll_by(amount * (h * 0.9 if args[2] == "pages" else 40 * self.zoom))

    def _on_wheel(self, event, linux: int | None = None) -> None:
        steps = linux if linux is not None else (event.delta / 120 if abs(event.delta) >= 120 else (1 if event.delta > 0 else -1))
        if event.state & 0x4:  # Strg gedrückt
            self.change_zoom(ZOOM_STEP * (1 if steps > 0 else -1))
        else:
            self._scroll_by(-steps * 60 * self.zoom)

    def change_zoom(self, delta: float | None) -> None:
        new = 1.0 if delta is None else round(min(3.0, max(0.5, self.settings.page_zoom + delta)), 2)
        if new == self.settings.page_zoom:
            return
        self.settings.page_zoom = new
        for st in self.states.values():
            st.layout_key = None
        if self.active:
            self._request_layout(self.active)
        self._set_status(f"Zoom {round(new * 100)} %")
        self._save_settings()

    def _link_at(self, x: float, y: float) -> str | None:
        st = self.active
        if not st or not st.layout:
            return None
        px, py = x, y + st.scroll
        for cmd in st.links:
            if cmd.x <= px <= cmd.x + cmd.width and cmd.y - 2 <= py <= cmd.y + cmd.size * 1.3:
                return cmd.href
        return None

    def _on_motion(self, event) -> None:
        href = self._link_at(event.x, event.y)
        self.canvas.configure(cursor="hand2" if href else "")
        if href and self.active and self.active.page:
            self._set_status(resolve_link(self.active.page.url, href) or f"{href} (wird nicht geöffnet)")
        elif not href:
            self._set_status("")

    def _on_click(self, event, force_new_tab: bool = False) -> None:
        self.canvas.focus_set()
        href = self._link_at(event.x, event.y)
        st = self.active
        if not href or not st or not st.page:
            return
        target = resolve_link(st.page.url, href)
        if target is None:
            self._set_status(f"Dieser Link wird aus Sicherheitsgründen nicht geöffnet: {href}")
            return
        if force_new_tab or event.state & 0x4:
            self.new_tab(target, activate=False)
        else:
            self.navigate(st.id, target)

    # ----------------------------------------------------------------------------- Modi, Gaming, Ruhezustand
    def set_mode(self, mode: Mode) -> None:
        self.session.modes.set_base(mode)
        self.settings.mode = mode.value
        self._update_status()
        self._save_settings()

    def toggle_gaming(self) -> None:
        enabled = bool(self.var_gaming.get())
        self.settings.gaming_detection = enabled
        (self.detector.enable if enabled else self.detector.disable)()
        self._set_status("Gaming-Erkennung an (nur lokal)." if enabled else "Gaming-Erkennung aus.")
        self._save_settings()

    def toggle_autoswitch(self) -> None:
        self.settings.gaming_auto_switch = self.session.modes.gaming_auto_switch = bool(self.var_autoswitch.get())
        self._save_settings()

    def _tick_sleep(self) -> None:
        if self._closing:
            return
        for tab_id in self.session.tick(time.monotonic()):
            st = self.states.get(tab_id)
            if st is None or st.loading:
                self.session.tabs.tabs[tab_id].suspended = False
                continue
            if st.page is not None:
                st.page.document = None  # Speicher freigeben; beim Aktivieren wird neu geladen
            st.layout = st.layout_key = None
            st.links = []
            self._style_tab(st)
        self.root.after(15_000, self._tick_sleep)

    def _tick_gaming(self) -> None:
        if self._closing:
            return
        if self.detector.enabled and not self._poll_busy:
            self._poll_busy = True
            self.pool.submit(self._gaming_job)
        self.root.after(5_000, self._tick_gaming)

    def _gaming_job(self) -> None:
        try:
            self.detector.poll()
        finally:
            self._poll_busy = False

    # ----------------------------------------------------------------------------- Status, Menü, Einstellungen
    def _set_status(self, text: str) -> None:
        self._status_msg = text
        self.var_status.set(text)

    def _update_status(self) -> None:
        mode = self.session.modes.mode
        sleep = self.session.modes.profile.tab_sleep_after_s
        extra = f", Tabs schlafen nach {sleep // 60 if sleep >= 120 else sleep} {'Min.' if sleep >= 120 else 's'}" if sleep else ""
        self.var_mode.set(f"Modus: {MODE_LABELS[mode]}{extra}")

    def _update_nav(self) -> None:
        hist = self.session.history.get(self.active_id) if self.active_id is not None else None
        for btn, enabled in ((self.btn_back, bool(hist and hist.can_back)), (self.btn_fwd, bool(hist and hist.can_forward))):
            btn.configure(fg=self.theme.fg if enabled else self.theme.surface, cursor="hand2" if enabled else "")

    def _open_menu(self) -> None:
        x = self.btn_menu.winfo_rootx()
        y = self.btn_menu.winfo_rooty() + self.btn_menu.winfo_height()
        self.menu.tk_popup(x, y)

    def _save_settings(self) -> None:
        if self.settings_path is None:
            return
        try:
            self.settings.save(self.settings_path)
        except OSError:
            self._set_status("Einstellungen konnten nicht gespeichert werden.")

    def _on_callback_error(self, exc, val, tb) -> None:
        log_crash("".join(traceback.format_exception(exc, val, tb)))
        self._set_status("Interner Fehler – Details stehen in crash.log.")

    def quit(self) -> None:
        self._closing = True
        self._save_settings()
        try:
            self.root.destroy()
        except tk.TclError:
            pass


# --------------------------------------------------------------------------------- Start
def log_crash(text: str) -> None:
    try:
        path = default_settings_path().with_name("crash.log")
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(f"--- {time.strftime('%Y-%m-%d %H:%M:%S')} Nexlori {__version__}\n{text}\n")
    except OSError:
        pass


def _enable_dpi_awareness() -> None:
    if sys.platform != "win32":
        return
    try:
        import ctypes

        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:  # noqa: BLE001 - ältere Windows-Versionen
            ctypes.windll.user32.SetProcessDPIAware()
    except Exception:  # noqa: BLE001
        pass


def run(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    sys.setrecursionlimit(3000)  # tief verschachtelte Seiten; Überschreitung wird als Fehlerseite gemeldet
    _enable_dpi_awareness()
    path = default_settings_path()
    try:
        settings = Settings.load(path)
    except (ValueError, OSError):  # beschädigte Datei: mit Standardwerten starten
        settings = Settings()
    try:
        root = tk.Tk()
        start = "about:start"
        urls = [a for a in argv if not a.startswith("-")]
        if urls:
            start = BrowserSession(settings).resolve_input(" ".join(urls))
        NexloriApp(root, settings, path, start)
        root.mainloop()
        return 0
    except Exception:  # noqa: BLE001
        text = traceback.format_exc()
        log_crash(text)
        try:
            messagebox.showerror("Nexlori", "Nexlori ist unerwartet beendet worden.\n\nDetails stehen in crash.log:\n" + str(path.with_name("crash.log")))
        except Exception:  # noqa: BLE001
            pass
        return 1
