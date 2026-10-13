import pytest

from nexlori.spotify_links import normalize_spotify_url


def test_track_album_playlist_links_become_spotify_embeds():
    track = normalize_spotify_url("https://open.spotify.com/track/1234567890abcdefghijklm")
    assert track.startswith("https://open.spotify.com/embed/track/1234567890abcdefghijklm")
    assert normalize_spotify_url("open.spotify.com/playlist/1234567890abcdefghijklm").startswith(
        "https://open.spotify.com/embed/playlist/"
    )
    assert normalize_spotify_url("https://open.spotify.com/embed/album/1234567890abcdefghijklm").endswith(
        "/embed/album/1234567890abcdefghijklm"
    )


def test_non_spotify_hosts_are_rejected():
    with pytest.raises(ValueError, match="Spotify"):
        normalize_spotify_url("https://evil.example/track/1234567890abcdefghijklm")
    with pytest.raises(ValueError, match="Spotify"):
        normalize_spotify_url("javascript:alert(1)")


def test_unknown_embed_type_is_rejected():
    with pytest.raises(ValueError, match="Einbettungstyp"):
        normalize_spotify_url("https://open.spotify.com/embed/unknown/1234567890")


def test_empty_or_home_link_uses_spotify_home():
    assert normalize_spotify_url("") == "https://open.spotify.com/"
    assert normalize_spotify_url("https://open.spotify.com/") == "https://open.spotify.com/"
