import pytest

from nexlori.engine import Document, paint, render_html
from nexlori.engine.layout import MonospaceMetrics, Rect, Text

M = MonospaceMetrics()


def run(html, width=300):
    return render_html(html, width, metrics=M).layout


def texts(layout):
    return [c for c in layout.commands if isinstance(c, Text)]


def test_link_text_carries_href_and_measured_width():
    t = texts(run('<div>vor <a href="/x">Link Text</a> nach</div>'))
    assert [x.text for x in t] == ["vor", "Link Text", "nach"]  # Link wird nicht mit Nachbartext verschmolzen
    assert [x.href for x in t] == [None, "/x", None]
    assert t[1].width == pytest.approx(9.6 * 9)


def test_block_level_link_and_nested_inline_keep_href():
    t = texts(run('<style>a { display: block }</style><a href="/y">Text <b>fett</b></a>'))
    assert {x.href for x in t} == {"/y"}


def test_anchor_without_href_is_not_a_link():
    assert texts(run("<div><a name=top>x</a></div>"))[0].href is None


def test_zoom_scales_lengths_and_fonts_and_can_be_reset():
    doc = Document.from_html('<div style="width:100px;height:10px;background:red">x</div>')

    def box(zoom):
        lay = doc.layout(400, M, zoom)
        return [c for c in lay.commands if isinstance(c, Rect)][0], texts(lay)[0]

    rect, text = box(2.0)
    assert (rect.w, rect.h, text.size) == (200, 20, 32)
    rect, text = box(1.0)
    assert (rect.w, rect.h, text.size) == (100, 10, 16)


def test_document_title_and_layout_cache():
    doc = Document.from_html("<title>  Meine \n Seite </title><p>x</p>")
    assert doc.title == "Meine Seite"
    assert Document.from_html("<p>x</p>").title == ""
    assert doc.layout(300, M) is doc.layout(300, M)
    assert doc.layout(300, M) is not doc.layout(200, M)


def test_hidden_attribute_and_unrenderable_elements_are_not_shown():
    t = texts(run('<p hidden>a</p><svg><title>b</title></svg><video>c</video><select><option>d</option></select><p>e</p>'))
    assert [x.text for x in t] == ["e"]


def test_table_cells_flow_as_stacked_blocks():
    t = texts(run("<table><tr><td>a</td><td>b</td></tr><tr><td>c</td></tr></table>"))
    assert [x.text for x in t] == ["a", "b", "c"]
    assert t[0].y < t[1].y < t[2].y


def test_hr_draws_a_thin_line():
    rects = [c for c in run("<hr>").commands if isinstance(c, Rect)]
    assert len(rects) == 1 and rects[0].h == 1 and rects[0].w == 300 - 0


def test_universal_tag_id_and_class_rules_all_apply_through_the_index():
    html = (
        "<style>* { margin: 0 } p { color: #ff0000 } .a { background: #00ff00 } #z { color: #0000ff }"
        " .a.b { padding: 4px } div p { font-size: 20px }</style>"
        '<div><p class="a b" id="z">t</p><p>u</p></div>'
    )
    doc = Document.from_html(html)
    p1, p2 = doc.dom.find_all("p")
    assert p1.style.color == (0, 0, 255) and p1.style.background == (0, 255, 0)
    assert p1.style.padding == [4.0] * 4 and p1.style.margin == [0.0] * 4
    assert p2.style.color == (255, 0, 0) and p2.style.background is None and p2.style.font_size == 20


def test_repeated_class_names_do_not_duplicate_rules():
    doc = Document.from_html("<style>.a { margin-top: 3px }</style><p class='a a a'>x</p>")
    assert doc.dom.find_all("p")[0].style.margin[0] == 3.0


def test_paint_clip_draws_only_the_requested_slice():
    pytest.importorskip("PIL")
    html = '<body style="margin:0"><div style="height:100px;background:#ff0000"></div><div style="height:100px;background:#0000ff"></div></body>'
    lay = run(html, 40)
    full = paint(lay)
    assert full.size == (40, 200)
    part = paint(lay, top=100, height=50)
    assert part.size == (40, 50)
    assert part.getpixel((5, 5)) == (0, 0, 255)
    assert paint(lay, top=50, height=100).getpixel((5, 10)) == (255, 0, 0)
    assert paint(lay, top=50, height=100).getpixel((5, 60)) == (0, 0, 255)
    assert paint(lay, top=180, height=100).size == (40, 100)  # über das Seitenende hinaus: kein Fehler
