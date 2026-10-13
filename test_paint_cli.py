import pytest

pytest.importorskip("PIL")

from nexlori.__main__ import main  # noqa: E402
from nexlori.engine import render_html  # noqa: E402


def test_canvas_background_and_boxes_are_painted():
    html = (
        '<body style="margin:0;background:#ff0000">'
        '<div style="height:10px;width:20px;background:#00ff00"></div>'
        '<div style="height:10px"></div></body>'
    )
    img = render_html(html, 50).to_image()
    assert img.size == (50, 20)
    assert img.getpixel((5, 5)) == (0, 255, 0)
    assert img.getpixel((30, 5)) == (255, 0, 0)  # Body-Hintergrund färbt die ganze Fläche
    assert img.getpixel((5, 15)) == (255, 0, 0)


def test_text_is_actually_drawn():
    img = render_html("<p>Hallo Welt</p>", 200).to_image()
    assert len({img.getpixel((x, y)) for x in range(8, 100) for y in range(16, 40)}) > 1


def test_border_pixels():
    img = render_html('<body style="margin:0"><div style="border:2px solid #0000ff;height:20px"></div></body>', 40).to_image()
    assert img.getpixel((0, 10)) == (0, 0, 255) and img.getpixel((20, 1)) == (0, 0, 255)
    assert img.getpixel((20, 12)) == (255, 255, 255)


def test_cli_render_and_themes(tmp_path, capsys):
    src, out = tmp_path / "a.html", tmp_path / "a.png"
    src.write_text("<h1>Titel</h1><p>Text</p>", encoding="utf-8")
    assert main(["render", str(src), str(out), "--width", "320"]) == 0
    assert out.exists() and out.stat().st_size > 0
    assert main(["themes"]) == 0
    assert "pride-trans" in capsys.readouterr().out
