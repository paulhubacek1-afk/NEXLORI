import gzip
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from nexlori.net import FetchError, decode_body, fetch_url, safe_url


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):  # Testausgabe ruhig halten
        pass

    def _send(self, body, ctype="text/html; charset=utf-8", status=200, extra=None):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path
        if path == "/":
            self._send("<title>Hallo</title><p>Grüße</p>".encode())
        elif path == "/latin":
            self._send(b"<p>gr\xfc\xdfe</p>", "text/html; charset=iso-8859-1")
        elif path == "/meta":
            self._send(b'<meta charset="windows-1252"><p>\xe4</p>', "text/html")
        elif path == "/gz":
            self._send(gzip.compress("<p>komprimiert ä</p>".encode()), extra={"Content-Encoding": "gzip"})
        elif path == "/bomb":
            self._send(gzip.compress(b"a" * (20 * 1024 * 1024)), extra={"Content-Encoding": "gzip"})
        elif path == "/big":
            self._send(b"<p>" + b"x" * (4 * 1024 * 1024))
        elif path == "/redirect":
            self._send(b"", status=302, extra={"Location": "/"})
        elif path == "/redir-ftp":
            self._send(b"", status=302, extra={"Location": "ftp://example.com/x"})
        elif path == "/plain":
            self._send(b"zeile 1\nzeile 2", "text/plain; charset=utf-8")
        elif path == "/img":
            self._send(b"\x89PNG....", "image/png")
        elif path == "/404":
            self._send(b"<h1>Nicht da</h1>", status=404)
        elif path == "/slow":
            time.sleep(2)
            self._send(b"spaet")
        elif path.startswith("/echo"):
            self._send(f"<p>{self.headers.get('User-Agent')}|{self.headers.get('Cookie')}|{self.path}</p>".encode())
        else:
            self._send(b"?", status=500)


@pytest.fixture(scope="module")
def base():
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


def get(base, path, **kw):
    return fetch_url(base + path, use_system_proxy=False, **kw)


def test_basic_fetch(base):
    r = get(base, "/")
    assert (r.status, r.content_type, r.truncated) == (200, "text/html", False)
    assert "Grüße" in r.text and r.url == base + "/"


def test_charset_from_header_and_from_meta(base):
    assert "grüße" in get(base, "/latin").text
    assert "ä" in get(base, "/meta").text


def test_gzip_is_decoded(base):
    assert "komprimiert ä" in get(base, "/gz").text


def test_size_limit_and_zip_bomb_protection(base):
    big = get(base, "/big", max_bytes=1024 * 1024)
    assert big.truncated and len(big.text) <= 1024 * 1024
    bomb = get(base, "/bomb", max_bytes=1024 * 1024)
    assert bomb.truncated and len(bomb.text) <= 1024 * 1024


def test_redirects_are_followed_but_only_to_http(base):
    r = get(base, "/redirect")
    assert r.url == base + "/" and "Hallo" in r.text
    with pytest.raises(FetchError, match="blockiert"):
        get(base, "/redir-ftp")


def test_plain_text_is_allowed_and_binary_is_rejected(base):
    assert get(base, "/plain").content_type == "text/plain"
    with pytest.raises(FetchError, match="image/png"):
        get(base, "/img")


def test_http_errors_still_return_the_page(base):
    r = get(base, "/404")
    assert r.status == 404 and "Nicht da" in r.text


def test_timeout_becomes_a_readable_error(base):
    with pytest.raises(FetchError, match="Zeitüberschreitung"):
        get(base, "/slow", timeout=0.4)


def test_connection_refused_becomes_a_readable_error():
    # Unter Windows meldet ein abgelehnter Verbindungsaufbau mitunter erst nach einer Zeitüberschreitung.
    with pytest.raises(FetchError, match="nicht erreichbar|Zeitüberschreitung"):
        fetch_url("http://127.0.0.1:1/", use_system_proxy=False, timeout=2)


def test_only_http_and_https_are_fetched():
    for url in ("ftp://example.com/", "file:///etc/passwd", "javascript:alert(1)", "data:text/html,x"):
        with pytest.raises(FetchError, match="nicht unterstützt"):
            fetch_url(url)


def test_no_cookies_are_sent_and_user_agent_is_set(base):
    text = get(base, "/echo?q=ä b").text
    assert "Nexlori/" in text and "|None|" in text
    assert "q=%C3%A4%20b" in text


def test_safe_url_normalizes_without_credentials_or_fragment():
    assert safe_url("https://user:pw@Bücher.example/Pfad mit Leer?x=ä#frag") == \
        "https://xn--bcher-kva.example/Pfad%20mit%20Leer?x=%C3%A4"
    assert safe_url("http://[::1]:8080") == "http://[::1]:8080/"
    for bad in ("http://", "http://host:notaport/"):
        with pytest.raises(FetchError):
            safe_url(bad)


def test_decode_body_fallbacks():
    assert decode_body("ä".encode(), None) == "ä"
    assert decode_body(b"\xe4", "unbekannte-kodierung") == "\ufffd"
    assert decode_body("ä".encode("utf-16"), "utf-16") == "ä"
