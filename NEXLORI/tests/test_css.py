import pytest

from nexlori.engine.css import (
    compute_styles, parse_color, parse_length, parse_selector, parse_stylesheet,
)
from nexlori.engine.dom import parse_html


def styled(html, css=""):
    dom = parse_html(html)
    compute_styles(dom, [parse_stylesheet(css)])
    return dom


def style_of(dom, tag):
    return dom.find_all(tag)[0].style


def test_colors():
    assert parse_color("#fff") == (255, 255, 255)
    assert parse_color("#1A2b3C") == (26, 43, 60)
    assert parse_color("rgb(1, 2,3)") == (1, 2, 3)
    assert parse_color("Teal") == (0, 128, 128)
    assert parse_color("transparent") is None
    for bad in ("#12", "rgb(300,0,0)", "nope", "#gggggg"):
        with pytest.raises(ValueError):
            parse_color(bad)


def test_lengths():
    assert parse_length("12px", 16) == 12
    assert parse_length("1.5em", 10) == 15
    assert parse_length("2rem", 10) == 32
    assert parse_length("12pt", 10) == 16
    assert parse_length("50%", 10) == "50%"
    assert parse_length("0", 10) == 0
    assert parse_length("auto", 10) == "auto"
    with pytest.raises(ValueError):
        parse_length("12", 10)


def test_selector_matching_and_specificity():
    dom = parse_html('<div class="a"><p id="x" class="b c">t</p></div>')
    p = dom.find_all("p")[0]
    assert parse_selector("p").matches(p)
    assert parse_selector(".a p").matches(p)
    assert parse_selector(".a > p").matches(p)
    assert not parse_selector("body > p").matches(p)
    assert parse_selector("p.b.c#x").matches(p)
    assert not parse_selector(".zzz").matches(p)
    assert parse_selector("#x").specificity > parse_selector(".b.c").specificity > parse_selector("p").specificity


def test_unsupported_selectors_are_dropped():
    assert parse_selector("a:hover") is None
    assert parse_selector("a[href]") is None
    assert parse_selector("a + b") is None
    assert parse_stylesheet("a:hover { color: red } p { color: blue }")[0].declarations[0][1] == "blue"


def test_at_rules_are_skipped_not_applied():
    rules = parse_stylesheet("@media print { p { color: red } } @import url(x); p { color: blue }")
    assert len(rules) == 1 and rules[0].declarations[0][1] == "blue"


def test_comments_are_ignored():
    assert len(parse_stylesheet("/* x { y } */ p { color: red /* c */ }")) == 1


def test_cascade_specificity_inline_important():
    css = "p { color: red } .x { color: blue } #y { color: green }"
    assert style_of(styled('<p class="x" id="y">t</p>', css), "p").color == (0, 128, 0)
    assert style_of(styled('<p id="y" style="color: black">t</p>', css), "p").color == (0, 0, 0)
    assert style_of(styled('<p id="y" style="color: black">t</p>', "#y { color: lime !important }"), "p").color == (0, 255, 0)


def test_later_rule_wins_on_equal_specificity():
    assert style_of(styled("<p>t</p>", "p { color: red } p { color: blue }"), "p").color == (0, 0, 255)


def test_inheritance_and_non_inherited_properties():
    dom = styled('<div style="color: red; font-size: 20px; margin: 10px; background: blue"><span>x</span></div>')
    span = style_of(dom, "span")
    assert span.color == (255, 0, 0) and span.font_size == 20
    assert span.margin == [0.0] * 4 and span.background is None


def test_em_uses_own_font_size_but_font_size_em_uses_parent():
    dom = styled('<div style="font-size: 20px"><p style="font-size: 2em; margin-top: 1em">x</p></div>')
    p = style_of(dom, "p")
    assert p.font_size == 40 and p.margin[0] == 40


def test_ua_defaults():
    dom = styled("<body><h1>t</h1><b>b</b><a>l</a><script>x</script></body>")
    assert style_of(dom, "h1").bold and style_of(dom, "h1").font_size == 32
    assert style_of(dom, "b").bold
    assert style_of(dom, "a").underline and style_of(dom, "a").color == (0, 0, 238)
    assert style_of(dom, "script").display == "none"
    assert style_of(dom, "body").margin == [8.0] * 4


def test_invalid_declarations_are_ignored():
    dom = styled('<p style="color: nope; margin: 1 2 3 4 5; padding: -3px; font-size: -2px">t</p>')
    p = style_of(dom, "p")
    assert p.color == (0, 0, 0) and p.padding == [0.0] * 4 and p.font_size == 16


def test_box_shorthands_and_border():
    dom = styled('<div style="margin: 1px 2px; padding: 1px 2px 3px; border: 2px solid #f00; width: 50%; height: 10px">x</div>')
    s = style_of(dom, "div")
    assert s.margin == [1, 2, 1, 2] and s.padding == [1, 2, 3, 2]
    assert (s.border_width, s.border_style, s.border_color) == (2, "solid", (255, 0, 0))
    assert s.width == "50%" and s.height == 10


def test_border_without_style_is_not_drawn():
    s = style_of(styled('<div style="border-width: 3px">x</div>'), "div")
    assert s.effective_border == 0


def test_margin_auto_is_kept_for_horizontal_centering():
    s = style_of(styled('<div style="margin: 0 auto">x</div>'), "div")
    assert s.margin[1] == "auto" and s.margin[3] == "auto"
