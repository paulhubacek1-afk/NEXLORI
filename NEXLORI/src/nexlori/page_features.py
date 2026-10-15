"""Small, testable helpers for Nexlori's privacy and performance features."""
from __future__ import annotations

import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


TRACKING_KEYS = {
    "fbclid", "gclid", "dclid", "msclkid", "mc_cid", "mc_eid",
    "igshid", "vero_id", "oly_anon_id", "oly_enc_id", "wickedid",
    "rb_clickid", "s_cid", "ref_src",
}


def clean_tracking_url(raw_url: str) -> str:
    """Remove common tracking query parameters without changing the destination."""
    try:
        parts = urlsplit(str(raw_url))
    except ValueError:
        return str(raw_url)
    if parts.scheme.lower() not in {"http", "https"} or not parts.query:
        return str(raw_url)
    kept = []
    for key, value in parse_qsl(parts.query, keep_blank_values=True):
        normalized = key.casefold()
        if normalized in TRACKING_KEYS or normalized.startswith("utm_"):
            continue
        kept.append((key, value))
    query = urlencode(kept, doseq=True)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, query, parts.fragment))


def build_cookie_banner_script(enabled: bool) -> str:
    """Best-effort consent helper: click only explicit reject/necessary-only buttons."""
    enabled_literal = "true" if enabled else "false"
    # Deliberately uses exact button labels; it never clicks generic Accept/Agree buttons
    # and never hides/removes a banner when no rejection option is present.
    return f"""(() => {{
const state = window.__nexloriCookieCleanup || (window.__nexloriCookieCleanup = {{}});
state.enabled = {enabled_literal};
const rejectLabel = /^(?:reject(?: all| optional)?(?: cookies)?|reject all non-essential cookies|decline(?: all| optional)?(?: cookies)?|deny(?: all)?|only necessary(?: cookies)?|necessary only|essential only|nur notwendige(?: cookies)?|nur erforderliche(?: cookies)?|alle ablehnen|auswahl ablehnen|optionale cookies ablehnen|nur erforderliche cookies|ablehnen)$/i;
const visible = el => {{
  const box = el.getBoundingClientRect();
  const style = getComputedStyle(el);
  return box.width > 0 && box.height > 0 && style.visibility !== 'hidden' && style.display !== 'none';
}};
const scan = () => {{
  if (!state.enabled || !document.documentElement) return;
  const controls = document.querySelectorAll('button,[role="button"],input[type="button"],input[type="submit"]');
  for (const el of controls) {{
    if (el.dataset.nexloriConsentChecked === '1' || !visible(el) || el.disabled) continue;
    const label = String(el.innerText || el.getAttribute('aria-label') || el.value || '')
      .replace(/\s+/g, ' ').trim();
    if (!label || !rejectLabel.test(label)) continue;
    el.dataset.nexloriConsentChecked = '1';
    el.click();
    state.lastAction = label;
    state.lastActionAt = Date.now();
    break;
  }}
}};
state.scan = scan;
scan();
if (!state.observer && document.documentElement) {{
  state.observer = new MutationObserver(() => scan());
  state.observer.observe(document.documentElement, {{childList:true, subtree:true, attributes:true}});
}}
}})();"""


def clean_consent_button_labels() -> tuple[str, ...]:
    """Public, testable list of the explicit labels the helper is designed to click."""
    return (
        "Reject all", "Decline", "Only necessary", "Nur notwendige Cookies",
        "Alle ablehnen", "Optionale Cookies ablehnen",
    )
