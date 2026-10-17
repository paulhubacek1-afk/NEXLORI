"""Eingebaute Nexlori-Add-ons.

Alle Add-ons laufen lokal. Sie senden nichts ins Netz und erheben keine Daten.

Art der Add-ons (``kind``):
- ``script``: wird beim Laden jeder Seite eingesetzt (CSS/JavaScript im isolierten Skript-Kontext).
- ``engine``: wird von Nexlori selbst ausgeführt (Navigation, Tab-Verwaltung).
- ``action``: ein Befehl im Menü „Werkzeuge“ (nur sichtbar, wenn das Add-on aktiv ist).
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Mapping

_HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


@dataclass(frozen=True)
class Addon:
    id: str
    label: str
    description: str
    kind: str  # "script" | "engine" | "action"
    default: bool = False
    hint: str = ""  # Bedienungshinweis (Tastenkürzel)


ADDONS: tuple[Addon, ...] = (
    Addon("dark-pages", "Dunkle Webseiten",
          "Stellt helle Webseiten dunkel dar. Bilder und Videos behalten ihre Farben, bereits dunkle Seiten bleiben unverändert.",
          "script"),
    Addon("night-light", "Nachtlicht",
          "Legt einen warmen, augenschonenden Farbfilter über jede Seite.", "script"),
    Addon("cookie-banners", "Cookie-Banner ausblenden",
          "Blendet bekannte Cookie- und Einwilligungsbanner aus und gibt das Scrollen wieder frei.", "script"),
    Addon("video-speed", "Video-Geschwindigkeit",
          "Ändert die Wiedergabegeschwindigkeit von Videos auf jeder Seite.", "script",
          hint="Alt+↑ schneller · Alt+↓ langsamer · Alt+0 zurücksetzen"),
    Addon("scroll-top", "Nach-oben-Knopf",
          "Zeigt beim Scrollen einen sanft eingeblendeten Knopf, der zurück an den Seitenanfang springt.", "script"),
    Addon("clean-urls", "Saubere Links",
          "Entfernt Tracking-Parameter wie utm_*, fbclid oder gclid aus Adressen, bevor die Seite geladen wird.",
          "engine", default=True),
    Addon("https-first", "HTTPS bevorzugen",
          "Öffnet http-Adressen zuerst verschlüsselt. Fehlt HTTPS, fragt Nexlori vor dem unverschlüsselten Laden nach.",
          "engine"),
    Addon("tab-sleep", "Tabs schlafen legen",
          "Gibt den Speicher lange nicht benutzter Hintergrund-Tabs frei. Sie laden beim Anklicken neu.",
          "engine"),
    Addon("reader", "Lesemodus",
          "Zeigt Artikel ruhig und ohne Ablenkung in den Farben des aktiven Themes.", "action",
          default=True, hint="Strg+Alt+R"),
    Addon("pdf-export", "Seite als PDF speichern",
          "Speichert die aktuelle Webseite als PDF-Datei.", "action", default=True, hint="Strg+P"),
    Addon("screenshot", "Screenshot der Seite",
          "Speichert den sichtbaren Bereich der Seite als PNG-Bild.", "action", default=True,
          hint="Strg+Alt+S"),
)
ADDON_IDS = frozenset(addon.id for addon in ADDONS)


def addon_by_id(addon_id: str) -> Addon | None:
    return next((a for a in ADDONS if a.id == addon_id), None)


def default_states() -> dict[str, bool]:
    return {addon.id: addon.default for addon in ADDONS}


def is_enabled(states: Mapping[str, bool], addon_id: str) -> bool:
    return bool(states.get(addon_id, False))


def _hex(value: str) -> str:
    if not _HEX_RE.match(value):
        raise ValueError(f"ungültige Farbe: {value!r}")
    return value


_COOKIE_SELECTORS = (
    "#onetrust-consent-sdk", "#onetrust-banner-sdk", "#CybotCookiebotDialog", "#CybotCookiebotDialogBodyUnderlay",
    "#usercentrics-root", "#usercentrics-cmp-ui", "#didomi-host", ".didomi-popup-container", ".didomi-popup-backdrop",
    "#qc-cmp2-container", ".qc-cmp2-container", ".cky-consent-container", ".cky-overlay", "#cookie-law-info-bar",
    ".cc-window", ".cc-banner", "#cookieconsent", ".cookie-consent", "#BorlabsCookieBox", ".BorlabsCookie",
    "#cmplz-cookiebanner-container", ".cmplz-cookiebanner", "[id^='sp_message_container']", "#truste-consent-track",
    ".truste_overlay", "#cookie-banner", "#cookiebanner", ".cookie-banner", "#cookie-notice", ".cookie-notice",
    "#gdpr-cookie-notice", "#gdpr-consent-tool-wrapper", ".fc-consent-root", "#consent-banner", ".consent-banner",
    "[aria-label*='cookie' i][role='dialog']", "[aria-label*='consent' i][role='dialog']",
)

_PRELUDE = """
const nx = (window.__nexloriAddons = window.__nexloriAddons || new Set());
const addon = (id, fn) => { if (nx.has(id)) return; nx.add(id); try { fn(); } catch (e) { /* Add-ons dürfen Seiten nie kaputt machen */ } };
const onRoot = fn => {
  if (document.documentElement) { fn(); return; }
  const o = new MutationObserver(() => { if (document.documentElement) { o.disconnect(); fn(); } });
  o.observe(document, {childList: true});
};
const onReady = fn => {
  if (document.readyState !== 'loading') fn(); else document.addEventListener('DOMContentLoaded', fn, {once: true});
};
const addStyle = (id, css) => onRoot(() => {
  if (document.getElementById(id)) return;
  const s = document.createElement('style'); s.id = id; s.textContent = css;
  (document.head || document.documentElement).appendChild(s);
});
"""

_JS: dict[str, str] = {
    "dark-pages": """
addon('dark-pages', () => {
  addStyle('nexlori-addon-dark-pages',
    'html.nexlori-dark{filter:invert(1) hue-rotate(180deg) !important;background:#fff !important}' +
    'html.nexlori-dark img,html.nexlori-dark video,html.nexlori-dark canvas,html.nexlori-dark picture,' +
    'html.nexlori-dark embed,html.nexlori-dark object{filter:invert(1) hue-rotate(180deg) !important}');
  onReady(() => {
    const lum = el => {
      if (!el) return null;
      const m = (getComputedStyle(el).backgroundColor.match(/[\\d.]+/g) || []).map(Number);
      if (m.length < 3 || (m.length > 3 && m[3] === 0)) return null;
      return (0.2126 * m[0] + 0.7152 * m[1] + 0.0722 * m[2]) / 255;
    };
    let l = lum(document.body);
    if (l === null) l = lum(document.documentElement);
    if (l !== null && l < 0.35) return;  // Seite ist bereits dunkel
    document.documentElement.classList.add('nexlori-dark');
  });
});
""",
    "night-light": """
addon('night-light', () => onRoot(() => {
  const d = document.createElement('div');
  d.id = 'nexlori-night-light';
  d.style.cssText = 'position:fixed;inset:0;pointer-events:none;z-index:2147483647;' +
    'background:rgba(255,147,41,.16);mix-blend-mode:multiply;';
  document.documentElement.appendChild(d);
}));
""",
    "cookie-banners": """
addon('cookie-banners', () => {
  const sels = __COOKIE_SELECTORS__;
  addStyle('nexlori-addon-cookie-banners', sels.join(',') + '{display:none !important}');
  onReady(() => {
    const present = () => sels.some(s => { try { return !!document.querySelector(s); } catch (e) { return false; } });
    const free = () => {
      if (!present()) return;
      for (const el of [document.documentElement, document.body]) {
        if (el && getComputedStyle(el).overflow === 'hidden') el.style.setProperty('overflow', 'auto', 'important');
      }
    };
    free(); setTimeout(free, 1500); setTimeout(free, 4000);
  });
});
""",
    "video-speed": """
addon('video-speed', () => {
  let hud = null, timer = 0;
  const show = text => {
    if (!hud) {
      hud = document.createElement('div');
      hud.style.cssText = 'position:fixed;top:18px;right:18px;padding:8px 14px;border-radius:12px;z-index:2147483647;' +
        'font:600 16px system-ui,sans-serif;background:__ACCENT__;color:__BG__;opacity:0;transition:opacity .2s;pointer-events:none';
      (document.body || document.documentElement).appendChild(hud);
    }
    hud.textContent = text; hud.style.opacity = '1';
    clearTimeout(timer); timer = setTimeout(() => { hud.style.opacity = '0'; }, 1200);
  };
  document.addEventListener('keydown', e => {
    if (!e.altKey || e.ctrlKey || e.metaKey) return;
    const t = e.target;
    if (t && (t.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName))) return;
    if (!['ArrowUp', 'ArrowDown', '0'].includes(e.key)) return;
    const vids = Array.from(document.querySelectorAll('video'));
    const v = vids.find(x => !x.paused && !x.ended) || vids[0];
    if (!v) return;
    let r = v.playbackRate;
    if (e.key === 'ArrowUp') r = Math.min(4, r + 0.25);
    else if (e.key === 'ArrowDown') r = Math.max(0.25, r - 0.25);
    else r = 1;
    v.playbackRate = r;
    show(String(Math.round(r * 100) / 100) + '×');
    e.preventDefault();
  }, true);
});
""",
    "scroll-top": """
addon('scroll-top', () => onReady(() => {
  const b = document.createElement('button');
  b.id = 'nexlori-scroll-top'; b.type = 'button'; b.textContent = '↑';
  b.setAttribute('aria-label', 'Nach oben');
  const hidden = 'opacity:0;transform:translateY(14px);pointer-events:none;';
  const shown = 'opacity:1;transform:none;pointer-events:auto;';
  const base = 'position:fixed;right:22px;bottom:22px;width:44px;height:44px;border-radius:50%;border:0;cursor:pointer;' +
    'background:__ACCENT__;color:__BG__;font:700 20px system-ui,sans-serif;z-index:2147483646;' +
    'box-shadow:0 6px 18px rgba(0,0,0,.35);transition:opacity .25s,transform .25s;';
  b.style.cssText = base + hidden;
  b.addEventListener('click', () => window.scrollTo({top: 0, behavior: 'smooth'}));
  const update = () => { b.style.cssText = base + (window.scrollY > 600 ? shown : hidden); };
  window.addEventListener('scroll', update, {passive: true});
  document.documentElement.appendChild(b);
}));
""",
}

_READER_JS = """
(() => {
  const ID = 'nexlori-reader';
  const old = document.getElementById(ID);
  if (old) { old.__close(); return 'closed'; }
  let best = null, bestLen = 0;
  for (const c of document.querySelectorAll('article, main, [role="main"], .post, .entry-content, #content, .content')) {
    const len = (c.innerText || '').length;
    if (len > bestLen) { best = c; bestLen = len; }
  }
  if (!best || bestLen < 400) {
    const sums = new Map();
    for (const p of document.querySelectorAll('p')) {
      const parent = p.parentElement;
      if (parent) sums.set(parent, (sums.get(parent) || 0) + (p.innerText || '').length);
    }
    let max = 0;
    for (const [el, n] of sums) if (n > max) { max = n; best = el; }
    bestLen = max;
  }
  if (!best || bestLen < 200) return 'no-article';
  const clone = best.cloneNode(true);
  clone.querySelectorAll('script,style,noscript,iframe,form,nav,aside,footer,button,input,select,textarea,svg,canvas,video,audio,object,embed,[hidden],[aria-hidden="true"]').forEach(n => n.remove());
  clone.querySelectorAll('*').forEach(n => {
    for (const a of Array.from(n.attributes)) {
      const name = a.name.toLowerCase();
      if (name.startsWith('on') || ['style', 'srcset', 'class', 'id'].includes(name)) n.removeAttribute(a.name);
    }
    if (n.tagName === 'A') {
      const href = n.getAttribute('href') || '';
      if (!/^https?:/i.test(href)) n.removeAttribute('href'); else n.setAttribute('rel', 'noopener noreferrer');
    }
  });
  const host = document.createElement('div');
  host.id = ID;
  host.style.cssText = 'position:fixed;inset:0;z-index:2147483647;';
  const root = host.attachShadow({mode: 'closed'});
  root.innerHTML = '<style>' +
    '.wrap{position:absolute;inset:0;overflow:auto;background:__BG__;color:__FG__;font:19px/1.75 Georgia,"Times New Roman",serif;animation:in .25s ease-out}' +
    '@keyframes in{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}' +
    'article{max-width:720px;margin:0 auto;padding:72px 24px 140px}' +
    'h1,h2,h3,h4{font-family:system-ui,"Segoe UI",sans-serif;line-height:1.25}' +
    'a{color:__ACCENT__}img{max-width:100%;height:auto;border-radius:8px}' +
    'pre{overflow:auto;background:rgba(127,127,127,.16);padding:12px;border-radius:8px}' +
    'blockquote{border-left:4px solid __ACCENT__;margin:1.2em 0;padding:.2em 1em;opacity:.92}' +
    '.close{position:fixed;top:14px;right:18px;width:40px;height:40px;border-radius:50%;border:0;cursor:pointer;' +
    'background:__ACCENT__;color:__BG__;font:700 22px system-ui,sans-serif}' +
    '</style><div class="wrap"><button class="close" aria-label="Lesemodus schließen">×</button><article></article></div>';
  const article = root.querySelector('article');
  if (!clone.querySelector('h1')) {
    const h = document.createElement('h1'); h.textContent = document.title; article.appendChild(h);
  }
  article.appendChild(clone);
  const close = () => { document.removeEventListener('keydown', onKey, true); host.remove(); };
  const onKey = e => { if (e.key === 'Escape') close(); };
  root.querySelector('.close').addEventListener('click', close);
  document.addEventListener('keydown', onKey, true);
  host.__close = close;
  document.documentElement.appendChild(host);
  return 'opened';
})();
"""


def build_addons_script(states: Mapping[str, bool], *, accent: str, bg: str) -> str:
    """JavaScript für alle aktiven ``script``-Add-ons (leer, wenn keines aktiv ist)."""
    parts = []
    for addon in ADDONS:
        if addon.kind == "script" and is_enabled(states, addon.id):
            parts.append(_JS[addon.id])
    if not parts:
        return ""
    body = _PRELUDE + "".join(parts)
    body = body.replace("__COOKIE_SELECTORS__", json.dumps(list(_COOKIE_SELECTORS)))
    body = body.replace("__ACCENT__", _hex(accent)).replace("__BG__", _hex(bg))
    return "(() => {\nif (window.top !== window) return;\n" + body + "\n})();"


def reader_script(*, bg: str, fg: str, accent: str) -> str:
    """Schaltet den Lesemodus ein/aus. Gibt 'opened', 'closed' oder 'no-article' zurück."""
    return (
        _READER_JS.replace("__BG__", _hex(bg)).replace("__FG__", _hex(fg)).replace("__ACCENT__", _hex(accent))
    )
