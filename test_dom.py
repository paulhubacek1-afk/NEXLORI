from nexlori.engine.dom import parse_html


def tags(root):
    return [n.tag for n in root.iter() if n.tag and n.tag != "#document"]


def test_nesting_and_attributes():
    root = parse_html('<div id=a class="x y"><span data-k=\'v\'>hi</span></div>')
    div = root.find_all("div")[0]
    assert div.attrs == {"id": "a", "class": "x y"}
    assert div.classes == ["x", "y"]
    assert div.find_all("span")[0].attrs["data-k"] == "v"
    assert div.text_content() == "hi"


def test_void_and_self_closing_elements_have_no_children():
    root = parse_html("<p>a<br>b<img src=x><br/>c</p>")
    assert [c.tag for c in root.find_all("p")[0].children] == [None, "br", None, "img", "br", None]


def test_implicit_end_tags_for_p_and_li():
    root = parse_html("<p>a<p>b<ul><li>x<li>y</ul>")
    assert len(root.find_all("p")) == 2
    assert all(p.parent is root for p in root.find_all("p"))
    assert [li.text_content() for li in root.find_all("li")] == ["x", "y"]


def test_nested_lists_do_not_close_outer_li():
    root = parse_html("<ul><li>a<ul><li>b</li></ul></li></ul>")
    outer = root.find_all("li")[0]
    assert len(outer.find_all("li")) == 2  # inklusive sich selbst


def test_script_and_style_are_raw_text():
    root = parse_html("<script>if (a<b && c>d) {}</script><style>p>a{}</style>")
    assert root.find_all("script")[0].text_content() == "if (a<b && c>d) {}"
    assert root.find_all("style")[0].text_content() == "p>a{}"


def test_comments_doctype_and_entities():
    root = parse_html("<!doctype html><!-- <b>x</b> --><p>T&amp;C &lt;3 &auml;</p>")
    assert tags(root) == ["p"]
    assert root.find_all("p")[0].text_content() == "T&C <3 ä"


def test_stray_end_tags_and_unclosed_elements_are_tolerated():
    root = parse_html("</b><div><span>x</div>y")
    assert tags(root) == ["div", "span"]
    assert root.text_content() == "xy"


def test_lone_angle_bracket_is_text():
    assert parse_html("a < b").text_content() == "a < b"


def test_tag_names_and_attribute_names_are_lowercased():
    root = parse_html('<DIV CLASS="A">x</DIV>')
    assert root.find_all("div")[0].attrs == {"class": "A"}
