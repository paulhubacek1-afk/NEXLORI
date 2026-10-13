"""Reliable per-document website-theme injection, kept independent from the Qt UI."""
from __future__ import annotations

import json

from .core.themes import Theme, page_theme_css


def build_page_theme_script(theme: Theme, enabled: bool) -> str:
    """Create the script attached to every page at DocumentReady and reused for the current page."""
    css_literal = json.dumps(page_theme_css(theme))
    enabled_literal = "true" if enabled else "false"
    return f"""(() => {{
const id = 'nexlori-theme-user-style';
window.__nexloriThemeConfig = {{enabled:{enabled_literal}, css:{css_literal}}};
const remove = () => {{
  const old = document.getElementById(id);
  if (old) old.remove();
}};
const ensure = () => {{
  const config = window.__nexloriThemeConfig;
  if (!document.documentElement || !config) return;
  if (!config.enabled) {{ remove(); return; }}
  let style = document.getElementById(id);
  if (!style) {{
    style = document.createElement('style');
    style.id = id;
    style.setAttribute('data-nexlori-user-theme', 'true');
    (document.head || document.documentElement).appendChild(style);
  }}
  if (style.textContent !== config.css) style.textContent = config.css;
}};
ensure();
if (!window.__nexloriThemeObserver) {{
  const observer = new MutationObserver(() => {{
    const config = window.__nexloriThemeConfig;
    if (!config) return;
    if (!config.enabled) {{ remove(); return; }}
    if (!document.getElementById(id)) ensure();
  }});
  if (document.documentElement) observer.observe(document.documentElement, {{childList:true, subtree:true}});
  window.__nexloriThemeObserver = observer;
}}
}})();"""
