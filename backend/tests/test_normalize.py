from procedurewriter.pipeline.normalize import normalize_html


def test_normalize_html_strips_scripts_and_nav():
    raw = b"""
    <html>
      <head><title>X</title><script>var secret = 1;</script></head>
      <body>
        <nav>Menu</nav>
        <h1>Heading</h1>
        <p>Paragraph one.</p>
        <p>Paragraph two.</p>
      </body>
    </html>
    """
    text = normalize_html(raw)
    assert "secret" not in text
    assert "Menu" not in text
    assert "Heading" in text
    assert "Paragraph one." in text

