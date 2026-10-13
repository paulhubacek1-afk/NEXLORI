import pytest

from nexlori.engine import render_html
from nexlori.engine.layout import Border, MonospaceMetrics, Rect, Text

M = MonospaceMetrics()  # 0,6 em je Zeichen -> 9,6 px bei 16 px; Zeilenhöhe 19,2 px


def run(html, width=300):
    return render_html(html, width, metrics=M).layout


def texts(layout):
    return [c for c in layout.commands if isinstance(c, Text)]


def test_blocks_stack_vertically():
    lay = run("<div>A</div><div>B</div>")
    a, b = texts(lay)
    assert (a.y, b.y) == (pytest.approx(1.6), pytest.approx(20.8))
    assert lay.height == pytest.approx(38.4)


def test_sibling_margins_collapse():
    lay = run('<p style="margin:10px 0">a</p><p style="margin:20px 0">b</p>')
    a, b = texts(lay)
    assert round(a.y, 1) == 11.6          # 10 + Halbführung 1,6
    assert round(b.y, 1) == 50.8          # 29,2 + max(10, 20) + 1,6
    assert round(lay.height, 1) == 88.4   # inkl. unterem Margin des letzten Kindes


def test_text_wraps_at_available_width_and_merges_same_style_words():
    lay = run("<div>aaaa bbbb cccc</div>", width=100)
    assert [t.text for t in texts(lay)] == ["aaaa bbbb", "cccc"]


def test_overlong_word_overflows_instead_of_looping():
    lay = run("<div>abcdefghijklmnop</div>", width=50)
    assert [t.text for t in texts(lay)] == ["abcdefghijklmnop"]


def test_br_creates_lines_and_double_br_a_blank_line():
    t = texts(run("<div>a<br>b</div>"))
    assert [x.text for x in t] == ["a", "b"] and t[1].y - t[0].y == pytest.approx(19.2)
    t = texts(run("<div>a<br><br>b</div>"))
    assert t[1].y - t[0].y == pytest.approx(38.4)


def test_display_none_is_skipped():
    t = texts(run('<div>a</div><div style="display:none">b</div><div>c</div>'))
    assert [x.text for x in t] == ["a", "c"] and t[1].y == pytest.approx(19.2 + 1.6)


def test_fixed_width_with_auto_margins_is_centered():
    rect = [c for c in run('<div style="width:100px;margin:0 auto;background:red">x</div>').commands if isinstance(c, Rect)][0]
    assert (rect.x, rect.w) == (100, 100)


def test_padding_and_border_are_part_of_the_box():
    lay = run('<div style="padding:10px;border:2px solid blue;background:#fff">x</div>')
    rect = [c for c in lay.commands if isinstance(c, Rect)][0]
    border = [c for c in lay.commands if isinstance(c, Border)][0]
    assert (rect.w, round(rect.h, 1)) == (300, 43.2)
    assert border.width == 2 and border.color == (0, 0, 255)
    assert texts(lay)[0].x == 12


def test_background_is_drawn_before_text():
    cmds = run('<div style="background:#fff">x</div>').commands
    assert isinstance(cmds[0], Rect) and isinstance(cmds[1], Text)


def test_text_align_center_and_right():
    assert round(texts(run('<div style="text-align:center">ab</div>', 200))[0].x, 1) == 90.4
    assert round(texts(run('<div style="text-align:right">ab</div>', 200))[0].x, 1) == 180.8


def test_lists_have_markers_and_indentation():
    t = texts(run("<ul><li>a</li><li>b</li></ul>"))
    assert [x.text for x in t] == ["\u2022", "a", "\u2022", "b"]
    assert t[1].x == 40 and round(t[0].x, 1) == 22.4
    t = texts(run("<ol><li>a</li><li>b</li></ol>"))
    assert [x.text for x in t if x.text.endswith(".")] == ["1.", "2."]


def test_inherited_color_and_bold_reach_inline_children():
    t = texts(run('<div style="color:red"><span>x <b>y</b></span></div>'))
    assert t[0].color == (255, 0, 0) and not t[0].bold
    assert t[1].text == "y" and t[1].bold


def test_space_between_differently_styled_inline_runs_is_kept():
    t = texts(run("<div>a <b>b</b> c</div>"))
    assert [x.text for x in t] == ["a", "b", "c"]
    assert t[1].x > t[0].x + 9.6 and t[2].x > t[1].x + 9.6


def test_links_are_underlined():
    lay = run('<div><a href="#">link</a></div>')
    assert any(isinstance(c, Rect) and c.color == (0, 0, 238) and c.h <= 1.5 for c in lay.commands)


def test_percentage_width_and_explicit_height():
    rect = [c for c in run('<div style="width:50%;height:30px;background:red"></div>').commands if isinstance(c, Rect)][0]
    assert (rect.w, rect.h) == (150, 30)


def test_whitespace_between_blocks_adds_no_space():
    assert run("<div>a</div>\n   \n<div>b</div>").height == pytest.approx(38.4)


def test_style_element_is_applied():
    t = texts(run("<style>p { color: #00ff00; margin: 0 }</style><p>x</p>"))
    assert t[0].color == (0, 255, 0)
