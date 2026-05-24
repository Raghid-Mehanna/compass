"""Tests for transform.transformer.clean_html.

The cleaning step strips nav/header/footer/script/style/etc. and prefers
the <main>/<article>/<body> region. These tests verify both behaviors
without needing Mongo or MinIO running.
"""

from transform.transformer import clean_html


def test_clean_html_strips_script_and_style():
    raw = (
        b"<html><head><style>body{color:red}</style></head>"
        b"<body><script>console.log('hi')</script>"
        b"<p>real content</p></body></html>"
    )
    out = clean_html(raw).decode("utf-8")
    assert "console.log" not in out
    assert "color:red" not in out
    assert "real content" in out


def test_clean_html_strips_nav_header_footer():
    raw = (
        b"<html><body>"
        b"<nav>NAV LINKS</nav>"
        b"<header>SITE HEADER</header>"
        b"<main><p>job description here</p></main>"
        b"<footer>SITE FOOTER</footer>"
        b"</body></html>"
    )
    out = clean_html(raw).decode("utf-8")
    assert "NAV LINKS" not in out
    assert "SITE HEADER" not in out
    assert "SITE FOOTER" not in out
    assert "job description here" in out


def test_clean_html_prefers_main_over_body():
    raw = (
        b"<html><body>"
        b"<div>page-level chrome</div>"
        b"<main><p>only this</p></main>"
        b"<div>more chrome</div>"
        b"</body></html>"
    )
    out = clean_html(raw).decode("utf-8")
    # When <main> exists, output should be just the <main> subtree.
    assert "only this" in out
    assert "page-level chrome" not in out
    assert "more chrome" not in out


def test_clean_html_falls_back_to_body_without_main():
    raw = b"<html><body><p>fallback content</p></body></html>"
    out = clean_html(raw).decode("utf-8")
    assert "fallback content" in out
