"""Theme-aware Nexlori start page HTML, kept independent of Qt for unit testing."""
from __future__ import annotations

import json
from html import escape as html_escape

from .core.themes import Theme, relative_luminance
from .links import PROJECT_LINKS


def build_start_page(
    theme: Theme,
    search_url: str,
    pride_mode: bool = False,
    bookmarks: list[dict[str, str]] | None = None,
) -> str:
    """A polished, theme-aware private start page; its animations never affect normal websites."""
    colors = ", ".join(theme.stripes or (theme.accent,))
    search_template = json.dumps(search_url, ensure_ascii=False)
    pride_visuals = (
        '<div class="pride-glow glow-a" aria-hidden="true"></div>'
        '<div class="pride-glow glow-b" aria-hidden="true"></div>'
        '<div class="pride-glow glow-c" aria-hidden="true"></div>'
        if pride_mode else ""
    )
    pride_css = """
.pride-glow { position:fixed; z-index:0; width:38vw; height:38vw; min-width:230px; min-height:230px;
  border-radius:50%; filter:blur(55px); opacity:.16; pointer-events:none; animation:pride-drift 17s ease-in-out infinite alternate; }
.glow-a { left:-13vw; top:10vh; background:#ff3b8d; }
.glow-b { right:-12vw; top:22vh; background:#35c8ff; animation-delay:-5s; }
.glow-c { left:34vw; bottom:-27vw; background:#a56bff; animation-delay:-9s; }
@keyframes pride-drift { from { transform:translate3d(0,-2vh,0) scale(.92); } to { transform:translate3d(2vw,3vh,0) scale(1.08); } }
""" if pride_mode else ""
    pride_pill = '<span class="pride-pill">✦ Pride colours in motion</span>' if pride_mode else ""
    bookmark_items = []
    for item in bookmarks or []:
        url = str(item.get("url", "")).strip()
        if not url.lower().startswith(("https://", "http://")):
            continue
        title = html_escape(str(item.get("title") or url)[:80])
        safe_url = html_escape(url, quote=True)
        bookmark_items.append(
            f'<a class="bookmark-chip" href="{safe_url}" title="{safe_url}"><span class="bookmark-star">☆</span><span>{title}</span></a>'
        )
    bookmark_markup = "".join(bookmark_items) or '<div class="empty-bookmarks">Noch keine Lesezeichen. Speichere eine Seite mit ☆ in der Browserleiste.</div>'
    project_markup = "".join(
        f'<a class="project-card" href="{html_escape(str(project["url"]), quote=True)}" target="_self">'
        f'<span class="project-icon">{html_escape(str(project.get("icon", "↗")))}</span>'
        f'<strong>{html_escape(str(project["title"]))}</strong>'
        f'<small>{html_escape(str(project.get("description", "")))}</small></a>'
        for project in PROJECT_LINKS
    )
    return f"""<!doctype html>
<html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Nexlori · Startseite</title>
<style>
:root {{ color-scheme: {'light' if relative_luminance(theme.bg) >= 0.5 else 'dark'}; }}
* {{ box-sizing:border-box }}
body {{ margin:0; min-height:100vh; overflow-x:hidden; background:{theme.bg}; color:{theme.fg}; font:16px 'Segoe UI',sans-serif; }}
main {{ position:relative; z-index:1; width:min(900px,92vw); margin:0 auto; padding:42px 0 36px; animation:page-enter .55s cubic-bezier(.2,.8,.2,1) both; }}
.stripe {{ height:5px; border-radius:5px; background:linear-gradient(90deg,{colors}); margin-bottom:32px; background-size:200% 100%; animation:stripe-flow 9s ease-in-out infinite alternate; }}
.mark {{ display:inline-block; color:{theme.accent}; font-size:12px; font-weight:800; letter-spacing:.22em; }}
h1 {{ margin:14px 0 8px; font-size:clamp(38px,6.5vw,68px); line-height:1.04; letter-spacing:-.055em; }}
p {{ color:{theme.fg}; opacity:.82; line-height:1.65; }}
.intro {{ max-width:650px; font-size:17px; }}
.pride-pill {{ display:inline-block; margin-top:14px; padding:7px 12px; border:1px solid {theme.accent}55; border-radius:100px; color:{theme.accent}; font-size:12px; }}
.bar {{ display:flex; gap:10px; background:{theme.surface}; border:1px solid {theme.accent}80; border-radius:20px; padding:9px; margin:28px 0 24px; box-shadow:0 16px 50px {theme.accent}16; transition:border-color .2s ease,transform .2s ease,box-shadow .2s ease; }}
.bar:focus-within {{ border-color:{theme.accent}; transform:translateY(-2px); box-shadow:0 18px 54px {theme.accent}25; }}
input {{ flex:1; min-width:0; border:0; outline:0; padding:13px; background:transparent; color:{theme.fg}; font:inherit; }}
button {{ background:{theme.accent}; color:{theme.bg}; border:0; border-radius:13px; padding:0 20px; font-weight:800; cursor:pointer; transition:transform .18s ease,filter .18s ease; }}
button:hover {{ transform:translateY(-1px); filter:brightness(1.08); }} button:active {{ transform:scale(.98); }}
.tiles {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(175px,1fr)); gap:12px; }}
a.tile {{ text-decoration:none; color:{theme.fg}; display:block; border:1px solid {theme.surface}; border-radius:17px; padding:19px; background:{theme.surface}; transition:transform .22s ease,border-color .22s ease,box-shadow .22s ease; animation:tile-enter .55s ease both; }}
a.tile:nth-child(2) {{ animation-delay:.05s; }} a.tile:nth-child(3) {{ animation-delay:.10s; }} a.tile:nth-child(4) {{ animation-delay:.15s; }} a.tile:nth-child(5) {{ animation-delay:.20s; }} a.tile:nth-child(6) {{ animation-delay:.25s; }}
a.tile:hover {{ border-color:{theme.accent}; transform:translateY(-4px); box-shadow:0 12px 30px {theme.accent}18; }}
a.tile:focus-visible, a.cta:focus-visible, button:focus-visible {{ outline:2px solid {theme.accent}; outline-offset:3px; }}
.tile-icon {{ transition:transform .24s ease,color .24s ease; }}
a.tile:hover .tile-icon {{ transform:translateY(-2px) rotate(-5deg) scale(1.1); }}
.community {{ margin:20px 0 22px; display:flex; justify-content:center; }}
a.cta {{ display:inline-flex; align-items:center; gap:10px; text-decoration:none; font-weight:600; color:{theme.bg}; background:{theme.accent}; padding:12px 24px; border-radius:999px; transition:transform .2s ease,box-shadow .2s ease; }}
a.cta:hover {{ transform:translateY(-2px); box-shadow:0 10px 26px {theme.accent}55; }}
.tile-icon {{ display:block; color:{theme.accent}; font-size:22px; margin-bottom:9px; }}
small {{ display:block; opacity:.68; margin-top:7px; line-height:1.45; }}
.foot {{ font-size:12px; margin-top:28px; opacity:.56; }}
.section-title {{ display:flex; align-items:center; justify-content:space-between; gap:12px; font-size:17px; letter-spacing:-.02em; margin:0 0 12px; }}
.bookmarks-section {{ margin:25px 0 28px; }}
.bookmark-list {{ display:flex; flex-wrap:wrap; gap:9px; }}
.bookmark-chip {{ display:inline-flex; align-items:center; gap:8px; max-width:100%; padding:9px 13px; background:{theme.surface}; color:{theme.fg}; border:1px solid {theme.surface}; border-radius:13px; text-decoration:none; font-size:13px; transition:transform .18s ease,border-color .18s ease; }}
.bookmark-chip:hover {{ border-color:{theme.accent}; transform:translateY(-2px); }}
.bookmark-star {{ color:{theme.accent}; font-size:16px; }}
.empty-bookmarks {{ opacity:.65; font-size:13px; padding:8px 0; }}
.projects-section {{ margin-top:29px; }}
.project-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(190px,1fr)); gap:10px; }}
.project-card {{ display:block; color:{theme.fg}; background:{theme.surface}; border:1px solid {theme.surface}; border-radius:16px; padding:16px; text-decoration:none; transition:transform .2s ease,border-color .2s ease,box-shadow .2s ease; }}
.project-card:hover {{ border-color:{theme.accent}; transform:translateY(-3px); box-shadow:0 10px 26px {theme.accent}18; }}
.project-icon {{ display:block; color:{theme.accent}; font-size:22px; margin-bottom:9px; }}
@keyframes page-enter {{ from {{ opacity:0; transform:translateY(9px); }} to {{ opacity:1; transform:translateY(0); }} }}
@keyframes tile-enter {{ from {{ opacity:0; transform:translateY(10px); }} to {{ opacity:1; transform:translateY(0); }} }}
@keyframes stripe-flow {{ from {{ background-position:0 0; }} to {{ background-position:100% 0; }} }}
{pride_css}
@media (prefers-reduced-motion:reduce) {{ *,*::before,*::after {{ animation:none !important; transition:none !important; }} }}
</style></head><body>{pride_visuals}<main><div class="stripe"></div><span class="mark">NEXLORI / BROWSER</span>
<h1>Das Web. Auf deine Art.</h1><p class="intro">Ein Browser, der sich deinem Stil anpasst – mit persönlicher Farbwelt, ruhiger Oberfläche und lokalem Schutz.</p>{pride_pill}
<form class="bar" id="search"><input id="query" autocomplete="off" autofocus placeholder="Suchen oder Webadresse eingeben" aria-label="Suchen oder Webadresse eingeben"><button type="submit">Los ↗</button></form>
<section class="bookmarks-section"><h2 class="section-title">Deine Lesezeichen</h2><div class="bookmark-list">{bookmark_markup}</div></section>
<div class="community"><a class="cta" href="nexlori://community/discord" title="Nexlori-Community auf Discord">💬 Discord-Community beitreten</a></div>
<div class="tiles">
<a class="tile" href="https://www.wikipedia.org/"><span class="tile-icon">⌕</span><strong>Wissen</strong><small>Wikipedia</small></a>
<a class="tile" href="https://www.youtube.com/"><span class="tile-icon">▶</span><strong>Video</strong><small>YouTube</small></a>
<a class="tile" href="https://github.com/"><span class="tile-icon">⌘</span><strong>Entwickeln</strong><small>GitHub</small></a>
<a class="tile" href="nexlori://addons"><span class="tile-icon">＋</span><strong>Add-ons</strong><small>Erweiterungen entdecken und verwalten</small></a>
<a class="tile" href="nexlori://home-network"><span class="tile-icon">⌂</span><strong>Heimnetz</strong><small>Router, NAS, Drucker und Smart Home</small></a>
<a class="tile" href="nexlori://settings"><span class="tile-icon">✦</span><strong>Dein Nexlori</strong><small>Themes, Suchmaschine und Einstellungen</small></a>
</div>{('<section class="projects-section"><h2 class="section-title">Meine Online-Projekte</h2><div class="project-grid">' + project_markup + '</div></section>') if project_markup else ''}<div class="foot">Nexlori · Chromium-WebEngine · Schutz und Einstellungen bleiben lokal.</div>
<script>
const template = {search_template};
document.getElementById('search').addEventListener('submit', function(e) {{
 e.preventDefault(); const q=document.getElementById('query').value.trim(); if(!q) return;
 const looksLikeUrl=/^(https?:\\/\\/|file:\\/\\/)/i.test(q) || (/^[^\\s]+\\.[^\\s]+$/.test(q) && !q.includes(' '));
 location.href=looksLikeUrl?(q.match(/^[a-z]+:\\/\\//i)?q:'https://'+q):template.replace("{{}}",encodeURIComponent(q));
}});
</script></main></body></html>"""
