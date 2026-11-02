from nexlori.game_page import game_page_html


def test_game_page_is_self_contained_and_has_controls():
    html = game_page_html()
    assert '<html lang="de">' in html
    assert 'id="board"' in html
    assert 'id="start"' in html
    assert 'id="pause"' in html
    assert 'nexlori-neon-snake-best' in html
    assert 'https://' not in html
